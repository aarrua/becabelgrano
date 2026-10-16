package ar.edu.utn.frsf.tanques.gateway;

import ar.edu.utn.frsf.tanques.audit.AuditService;
import ar.edu.utn.frsf.tanques.dto.ActuatorCommandResponse;
import ar.edu.utn.frsf.tanques.dto.BridgeAckMessage;
import ar.edu.utn.frsf.tanques.dto.BridgeCommandMessage;
import ar.edu.utn.frsf.tanques.dto.TelemetryFrame;
import ar.edu.utn.frsf.tanques.exception.ActuatorNotFoundException;
import ar.edu.utn.frsf.tanques.exception.BridgeUnavailableException;
import ar.edu.utn.frsf.tanques.exception.InterlockViolationException;
import ar.edu.utn.frsf.tanques.telemetry.TelemetryProvider;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.eclipse.paho.client.mqttv3.*;
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * Gateway de control de actuadores en perfil de producción (prod).
 * <p>
 * Publica comandos de control en 'tanques/cmd' (QoS 1, sin retain) y espera confirmación
 * asíncrona en 'tanques/ack' (QoS 1) correlacionando por 'id'.
 * Maneja reconexión automática y arranque tolerante a caídas del broker Mosquitto.
 */
@Component
@Profile("prod")
public class BridgeActuatorGateway implements ActuatorGateway, MqttCallbackExtended {

    private static final Logger log = LoggerFactory.getLogger(BridgeActuatorGateway.class);

    private final AuditService auditService;
    private final ObjectProvider<TelemetryProvider> telemetryProvider;
    private final ObjectMapper objectMapper;

    private final String mqttHost;
    private final int mqttPort;
    private final String mqttUser;
    private final String mqttPassword;
    private final String cmdTopic;
    private final String ackTopic;
    private final long timeoutMs;

    private final ConcurrentHashMap<String, CompletableFuture<BridgeAckMessage>> pendingAcks = new ConcurrentHashMap<>();
    private final Set<String> supportedTargets = Collections.newSetFromMap(new ConcurrentHashMap<>());

    private MqttClient mqttClient;
    private MqttConnectOptions connectOptions;
    private volatile boolean running = true;

    public BridgeActuatorGateway(
            AuditService auditService,
            ObjectProvider<TelemetryProvider> telemetryProvider,
            ObjectMapper objectMapper,
            @Value("${tanques.mqtt.host:localhost}") String mqttHost,
            @Value("${tanques.mqtt.port:1883}") int mqttPort,
            @Value("${tanques.mqtt.user:tanques}") String mqttUser,
            @Value("${tanques.mqtt.password:}") String mqttPassword,
            @Value("${tanques.mqtt.cmd-topic:tanques/cmd}") String cmdTopic,
            @Value("${tanques.mqtt.ack-topic:tanques/ack}") String ackTopic,
            @Value("${tanques.mqtt.timeout-ms:3000}") long timeoutMs
    ) {
        this.auditService = auditService;
        this.telemetryProvider = telemetryProvider;
        this.objectMapper = objectMapper;
        this.mqttHost = mqttHost;
        this.mqttPort = mqttPort;
        this.mqttUser = mqttUser;
        this.mqttPassword = mqttPassword;
        this.cmdTopic = cmdTopic;
        this.ackTopic = ackTopic;
        this.timeoutMs = timeoutMs;

        this.supportedTargets.add("pump");
    }

    /**
     * Constructor para pruebas con cliente MQTT inyectado.
     */
    public BridgeActuatorGateway(
            AuditService auditService,
            ObjectProvider<TelemetryProvider> telemetryProvider,
            ObjectMapper objectMapper,
            MqttClient mqttClient,
            String cmdTopic,
            String ackTopic,
            long timeoutMs
    ) {
        this(auditService, telemetryProvider, objectMapper, "localhost", 1883, "tanques", "", cmdTopic, ackTopic, timeoutMs);
        this.mqttClient = mqttClient;
        if (this.mqttClient != null) {
            this.mqttClient.setCallback(this);
        }
    }

    @PostConstruct
    public void start() {
        if (mqttClient == null) {
            initMqttClient();
        }
    }

    private void initMqttClient() {
        String serverUri = "tcp://" + mqttHost + ":" + mqttPort;
        String clientId = "tanques-backend-" + UUID.randomUUID().toString().replace("-", "").substring(0, 8);

        try {
            mqttClient = new MqttClient(serverUri, clientId, new MemoryPersistence());
            mqttClient.setCallback(this);

            connectOptions = new MqttConnectOptions();
            connectOptions.setCleanSession(true);
            connectOptions.setAutomaticReconnect(true);
            connectOptions.setConnectionTimeout(5);
            if (mqttUser != null && !mqttUser.isBlank()) {
                connectOptions.setUserName(mqttUser);
            }
            if (mqttPassword != null && !mqttPassword.isBlank()) {
                connectOptions.setPassword(mqttPassword.toCharArray());
            }

            // Hilo secundario para arranque tolerante: no bloquea el contexto de Spring si Mosquitto está caído
            Thread connectThread = new Thread(this::connectLoop, "tanques-backend-mqtt-connect");
            connectThread.setDaemon(true);
            connectThread.start();
        } catch (MqttException e) {
            log.error("Error al inicializar cliente Paho MQTT: {}", e.getMessage());
        }
    }

    private void connectLoop() {
        while (running && (mqttClient != null && !mqttClient.isConnected())) {
            try {
                log.info("Conectando con broker Mosquitto ({}:{})...", mqttHost, mqttPort);
                mqttClient.connect(connectOptions);
                break;
            } catch (MqttException e) {
                log.warn("Broker Mosquitto no disponible ({}:{}). Reintentando en 3 s...", mqttHost, mqttPort);
                try {
                    Thread.sleep(3000);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
    }

    @PreDestroy
    public void stop() {
        running = false;
        pendingAcks.clear();
        if (mqttClient != null) {
            try {
                if (mqttClient.isConnected()) {
                    mqttClient.disconnectForcibly(1000);
                }
                mqttClient.close();
            } catch (Exception e) {
                log.debug("Error cerrando cliente MQTT: {}", e.getMessage());
            }
        }
    }

    // =========================================================================
    // Callbacks MQTT (MqttCallbackExtended)
    // =========================================================================

    @Override
    public void connectComplete(boolean reconnect, String serverURI) {
        log.info("✓ Conexión con broker Mosquitto establecida (reconnect={}) en {}. Suscribiendo a '{}' (QoS 1)...",
                reconnect, serverURI, ackTopic);
        try {
            if (mqttClient != null && mqttClient.isConnected()) {
                mqttClient.subscribe(ackTopic, 1);
                log.info("✓ Suscripción activa en tópico de ACKs '{}'", ackTopic);
            }
        } catch (MqttException e) {
            log.error("Error suscribiendo a tópico de ACKs '{}': {}", ackTopic, e.getMessage());
        }
    }

    @Override
    public void connectionLost(Throwable cause) {
        log.warn("Conexión perdida con Mosquitto: {}. Reintento automático habilitado.",
                cause != null ? cause.getMessage() : "Desconexión inesperada");
    }

    @Override
    public void messageArrived(String topic, MqttMessage message) {
        // Callback no bloqueante: se procesa y completa el future de inmediato
        if (!ackTopic.equals(topic)) {
            return;
        }

        try {
            byte[] payload = message.getPayload();
            BridgeAckMessage ack = objectMapper.readValue(payload, BridgeAckMessage.class);

            if (ack != null && ack.ack() != null) {
                CompletableFuture<BridgeAckMessage> future = pendingAcks.get(ack.ack());
                if (future != null) {
                    future.complete(ack);
                } else {
                    log.warn("ACK recibido para comando no pendiente o ya expirado: ackId='{}'", ack.ack());
                }
            }
        } catch (Exception e) {
            log.error("Error al procesar mensaje ACK entrante desde '{}': {}", topic, e.getMessage());
        }
    }

    @Override
    public void deliveryComplete(IMqttDeliveryToken token) {
        // Publicación completada
    }

    // =========================================================================
    // Ejecución de Comandos y Consulta de Actuadores
    // =========================================================================

    @Override
    public ActuatorCommandResponse executeCommand(String target, boolean value, String username) {
        String normalized = target != null ? target.trim().toLowerCase() : "";
        if (!isValidTarget(normalized)) {
            auditService.recordCommand(username, normalized, value, false, "target_not_found");
            throw new ActuatorNotFoundException(normalized);
        }

        // Si se intenta ENCENDER la bomba, se requiere telemetría fresca (< 5 s)
        if (value) {
            TelemetryProvider provider = telemetryProvider.getIfAvailable();
            if (provider != null && !provider.isTelemetryFresh()) {
                String reason = "telemetry_stale";
                log.warn("Rechazo de encendido por telemetría desactualizada (> 5 s): target='{}', usuario='{}'", normalized, username);
                auditService.recordCommand(username, normalized, value, false, reason);
                throw new InterlockViolationException(normalized, value, reason,
                        "No se puede encender el actuador: la telemetría está desactualizada (> 5 s) y el estado físico del equipo no está verificado");
            }
        }

        String cmdId = "c_" + UUID.randomUUID().toString().replace("-", "").substring(0, 8);
        long nowMs = System.currentTimeMillis();
        BridgeCommandMessage cmdMsg = new BridgeCommandMessage(cmdId, "set", normalized, value, nowMs);

        CompletableFuture<BridgeAckMessage> future = new CompletableFuture<>();
        pendingAcks.put(cmdId, future);

        try {
            if (mqttClient == null || !mqttClient.isConnected()) {
                auditService.recordCommand(username, normalized, value, false, "bridge_unavailable");
                throw new BridgeUnavailableException(normalized, value, "bridge_unavailable",
                        "Control no disponible: sin conexión con el broker MQTT", cmdId);
            }

            byte[] payload = objectMapper.writeValueAsBytes(cmdMsg);
            MqttMessage mqttMsg = new MqttMessage(payload);
            mqttMsg.setQos(1);
            mqttMsg.setRetained(false);

            mqttClient.publish(cmdTopic, mqttMsg);
            log.info("Comando id='{}' publicado en '{}' (QoS 1): target='{}', valor={}", cmdId, cmdTopic, normalized, value);

            // Espera en el hilo del request HTTP con timeout de 3 s
            BridgeAckMessage ack = future.get(timeoutMs, TimeUnit.MILLISECONDS);

            if (ack.ok()) {
                auditService.recordCommand(username, normalized, value, true, null);
                log.info("✓ Comando id='{}' confirmado exitosamente por el bridge", cmdId);
                return ActuatorCommandResponse.success(cmdId, normalized, value);
            } else {
                String reason = ack.reason() != null ? ack.reason() : "unknown_rejection";
                auditService.recordCommand(username, normalized, value, false, reason);
                log.warn("Comando id='{}' rechazado: motivo='{}'", cmdId, reason);

                if ("device_timeout".equalsIgnoreCase(reason) || "expired".equalsIgnoreCase(reason)) {
                    throw new BridgeUnavailableException(normalized, value, reason,
                            "Comando no confirmado (" + reason + "): estado desconocido, verificar telemetría", cmdId);
                } else {
                    throw new InterlockViolationException(normalized, value, reason);
                }
            }
        } catch (TimeoutException te) {
            log.error("TIMEOUT: No se recibió ACK del bridge para id='{}' en {} ms", cmdId, timeoutMs);
            auditService.recordCommand(username, normalized, value, false, "bridge_unavailable");
            throw new BridgeUnavailableException(normalized, value, "bridge_unavailable",
                    "Tiempo de espera agotado sin confirmación: estado desconocido, verificar telemetría", cmdId);
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
            auditService.recordCommand(username, normalized, value, false, "interrupted");
            throw new BridgeUnavailableException(normalized, value, "interrupted",
                    "Ejecución interrumpida: estado desconocido, verificar telemetría", cmdId);
        } catch (ExecutionException ee) {
            Throwable cause = ee.getCause();
            String msg = cause != null ? cause.getMessage() : ee.getMessage();
            auditService.recordCommand(username, normalized, value, false, "error");
            throw new BridgeUnavailableException(normalized, value, "error",
                    "Error al esperar confirmación de comando: " + msg, cmdId);
        } catch (MqttException me) {
            auditService.recordCommand(username, normalized, value, false, "mqtt_error");
            throw new BridgeUnavailableException(normalized, value, "mqtt_error",
                    "Error de comunicación MQTT: " + me.getMessage(), cmdId);
        } catch (JsonProcessingException jpe) {
            auditService.recordCommand(username, normalized, value, false, "serialization_error");
            throw new RuntimeException("Error serializando comando MQTT", jpe);
        } finally {
            // Limpieza estricta para evitar fugas de memoria
            pendingAcks.remove(cmdId);
        }
    }

    @Override
    public Map<String, Boolean> getActuatorsState() {
        TelemetryProvider provider = telemetryProvider.getIfAvailable();
        Map<String, Boolean> state = new HashMap<>();

        if (provider != null) {
            try {
                TelemetryFrame frame = provider.getLatestTelemetry();
                if (frame != null && provider.isTelemetryFresh() && frame.actuators() != null && !frame.actuators().isEmpty()) {
                    return frame.actuators();
                }
            } catch (Exception e) {
                log.warn("No se pudo obtener el estado de actuadores desde la telemetría: {}", e.getMessage());
            }
        }

        // Si la telemetría tiene más de 5 s de antigüedad o no está disponible,
        // el estado se reporta como desconocido (null), nunca como 'apagada'
        state.put("pump", null);
        return state;
    }

    @Override
    public boolean isValidTarget(String target) {
        return target != null && supportedTargets.contains(target.trim().toLowerCase());
    }

    @Override
    public Set<String> getSupportedTargets() {
        return Collections.unmodifiableSet(supportedTargets);
    }

    public int getPendingAcksCount() {
        return pendingAcks.size();
    }

    public boolean isConnected() {
        return mqttClient != null && mqttClient.isConnected();
    }
}
