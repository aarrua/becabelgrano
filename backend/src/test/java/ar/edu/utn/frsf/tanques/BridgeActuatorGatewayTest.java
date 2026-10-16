package ar.edu.utn.frsf.tanques;

import ar.edu.utn.frsf.tanques.audit.AuditService;
import ar.edu.utn.frsf.tanques.dto.ActuatorCommandResponse;
import ar.edu.utn.frsf.tanques.dto.BridgeCommandMessage;
import ar.edu.utn.frsf.tanques.dto.TankTelemetry;
import ar.edu.utn.frsf.tanques.dto.TelemetryFrame;
import ar.edu.utn.frsf.tanques.exception.ActuatorNotFoundException;
import ar.edu.utn.frsf.tanques.exception.BridgeUnavailableException;
import ar.edu.utn.frsf.tanques.exception.InterlockViolationException;
import ar.edu.utn.frsf.tanques.gateway.BridgeActuatorGateway;
import ar.edu.utn.frsf.tanques.telemetry.TelemetryProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.eclipse.paho.client.mqttv3.MqttClient;
import org.eclipse.paho.client.mqttv3.MqttMessage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.ObjectProvider;

import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

class BridgeActuatorGatewayTest {

    private AuditService auditService;
    private ObjectProvider<TelemetryProvider> objectProvider;
    private TelemetryProvider telemetryProvider;
    private ObjectMapper objectMapper;
    private MqttClient mqttClient;
    private BridgeActuatorGateway gateway;

    private final String cmdTopic = "tanques/cmd";
    private final String ackTopic = "tanques/ack";

    @BeforeEach
    @SuppressWarnings("unchecked")
    void setUp() {
        auditService = mock(AuditService.class);
        objectProvider = mock(ObjectProvider.class);
        telemetryProvider = mock(TelemetryProvider.class);
        when(telemetryProvider.isTelemetryFresh()).thenReturn(true);
        when(objectProvider.getIfAvailable()).thenReturn(telemetryProvider);

        objectMapper = new ObjectMapper();
        mqttClient = mock(MqttClient.class);
        when(mqttClient.isConnected()).thenReturn(true);

        gateway = new BridgeActuatorGateway(
                auditService,
                objectProvider,
                objectMapper,
                mqttClient,
                cmdTopic,
                ackTopic,
                300 // Timeout corto para tests veloces
        );
    }

    @Test
    void testExecuteCommandSuccess() throws Exception {
        // Al publicar el comando capturamos el id enviado y simulamos la llegada del ACK exitoso
        doAnswer(invocation -> {
            MqttMessage msg = invocation.getArgument(1);
            BridgeCommandMessage cmd = objectMapper.readValue(msg.getPayload(), BridgeCommandMessage.class);

            Executors.newSingleThreadScheduledExecutor().schedule(() -> {
                try {
                    String ackJson = "{\"ack\":\"" + cmd.id() + "\",\"ok\":true}";
                    gateway.messageArrived(ackTopic, new MqttMessage(ackJson.getBytes()));
                } catch (Exception ignored) {
                }
            }, 30, TimeUnit.MILLISECONDS);

            return null;
        }).when(mqttClient).publish(eq(cmdTopic), any(MqttMessage.class));

        ActuatorCommandResponse response = gateway.executeCommand("pump", true, "docente");

        assertNotNull(response);
        assertTrue(response.ok());
        assertEquals("pump", response.target());
        assertTrue(response.value());
        assertNull(response.reason());

        verify(auditService).recordCommand("docente", "pump", true, true, null);
        assertEquals(0, gateway.getPendingAcksCount(), "El mapa de pendientes debe estar vacío");
    }

    @Test
    void testExecuteCommandInterlockRejection() throws Exception {
        doAnswer(invocation -> {
            MqttMessage msg = invocation.getArgument(1);
            BridgeCommandMessage cmd = objectMapper.readValue(msg.getPayload(), BridgeCommandMessage.class);

            Executors.newSingleThreadScheduledExecutor().schedule(() -> {
                try {
                    String ackJson = "{\"ack\":\"" + cmd.id() + "\",\"ok\":false,\"reason\":\"overflow_a\"}";
                    gateway.messageArrived(ackTopic, new MqttMessage(ackJson.getBytes()));
                } catch (Exception ignored) {
                }
            }, 20, TimeUnit.MILLISECONDS);

            return null;
        }).when(mqttClient).publish(eq(cmdTopic), any(MqttMessage.class));

        InterlockViolationException ex = assertThrows(InterlockViolationException.class, () ->
                gateway.executeCommand("pump", true, "docente")
        );

        assertEquals("pump", ex.getTarget());
        assertTrue(ex.isRequestedValue());
        assertEquals("overflow_a", ex.getReason());

        verify(auditService).recordCommand("docente", "pump", true, false, "overflow_a");
        assertEquals(0, gateway.getPendingAcksCount());
    }

    @Test
    void testExecuteCommandExpiredRejection() throws Exception {
        doAnswer(invocation -> {
            MqttMessage msg = invocation.getArgument(1);
            BridgeCommandMessage cmd = objectMapper.readValue(msg.getPayload(), BridgeCommandMessage.class);

            Executors.newSingleThreadScheduledExecutor().schedule(() -> {
                try {
                    String ackJson = "{\"ack\":\"" + cmd.id() + "\",\"ok\":false,\"reason\":\"expired\"}";
                    gateway.messageArrived(ackTopic, new MqttMessage(ackJson.getBytes()));
                } catch (Exception ignored) {
                }
            }, 20, TimeUnit.MILLISECONDS);

            return null;
        }).when(mqttClient).publish(eq(cmdTopic), any(MqttMessage.class));

        BridgeUnavailableException ex = assertThrows(BridgeUnavailableException.class, () ->
                gateway.executeCommand("pump", true, "docente")
        );

        assertEquals("pump", ex.getTarget());
        assertEquals("expired", ex.getReason());
        assertTrue(ex.getMessage().contains("estado desconocido, verificar telemetría"));

        verify(auditService).recordCommand("docente", "pump", true, false, "expired");
        assertEquals(0, gateway.getPendingAcksCount());
    }

    @Test
    void testExecuteCommandDeviceTimeout() throws Exception {
        doAnswer(invocation -> {
            MqttMessage msg = invocation.getArgument(1);
            BridgeCommandMessage cmd = objectMapper.readValue(msg.getPayload(), BridgeCommandMessage.class);

            Executors.newSingleThreadScheduledExecutor().schedule(() -> {
                try {
                    String ackJson = "{\"ack\":\"" + cmd.id() + "\",\"ok\":false,\"reason\":\"device_timeout\"}";
                    gateway.messageArrived(ackTopic, new MqttMessage(ackJson.getBytes()));
                } catch (Exception ignored) {
                }
            }, 20, TimeUnit.MILLISECONDS);

            return null;
        }).when(mqttClient).publish(eq(cmdTopic), any(MqttMessage.class));

        BridgeUnavailableException ex = assertThrows(BridgeUnavailableException.class, () ->
                gateway.executeCommand("pump", true, "docente")
        );

        assertEquals("pump", ex.getTarget());
        assertEquals("device_timeout", ex.getReason());
        assertTrue(ex.getMessage().contains("estado desconocido, verificar telemetría"));

        verify(auditService).recordCommand("docente", "pump", true, false, "device_timeout");
        assertEquals(0, gateway.getPendingAcksCount());
    }

    @Test
    void testExecuteCommandTimeout3sWithoutAck() {
        // El cliente publica pero nadie responde con ACK
        BridgeUnavailableException ex = assertThrows(BridgeUnavailableException.class, () ->
                gateway.executeCommand("pump", true, "docente")
        );

        assertEquals("pump", ex.getTarget());
        assertEquals("bridge_unavailable", ex.getReason());
        assertTrue(ex.getMessage().contains("Tiempo de espera agotado"));

        verify(auditService).recordCommand("docente", "pump", true, false, "bridge_unavailable");
        assertEquals(0, gateway.getPendingAcksCount(), "Debe limpiar el mapa de pendientes aún con timeout");
    }

    @Test
    void testExecuteCommandBrokerDisconnected() {
        when(mqttClient.isConnected()).thenReturn(false);

        BridgeUnavailableException ex = assertThrows(BridgeUnavailableException.class, () ->
                gateway.executeCommand("pump", true, "docente")
        );

        assertEquals("pump", ex.getTarget());
        assertEquals("bridge_unavailable", ex.getReason());
        assertTrue(ex.getMessage().contains("sin conexión con el broker MQTT"));

        verify(auditService).recordCommand("docente", "pump", true, false, "bridge_unavailable");
        assertEquals(0, gateway.getPendingAcksCount());
    }

    @Test
    void testReconnectionResumesReceivingAcks() throws Exception {
        // 1. Simular pérdida de conexión
        gateway.connectionLost(new RuntimeException("Broker caído temporalmente"));

        // 2. Simular reconexión exitosa invoca connectComplete
        gateway.connectComplete(true, "tcp://localhost:1883");

        // Verificar que se resuscribió al tópico de ACKs
        verify(mqttClient, atLeastOnce()).subscribe(eq(ackTopic), eq(1));

        // 3. Probar que tras la reconexión un nuevo comando se procesa correctamente
        doAnswer(invocation -> {
            MqttMessage msg = invocation.getArgument(1);
            BridgeCommandMessage cmd = objectMapper.readValue(msg.getPayload(), BridgeCommandMessage.class);

            Executors.newSingleThreadScheduledExecutor().schedule(() -> {
                try {
                    String ackJson = "{\"ack\":\"" + cmd.id() + "\",\"ok\":true}";
                    gateway.messageArrived(ackTopic, new MqttMessage(ackJson.getBytes()));
                } catch (Exception ignored) {
                }
            }, 20, TimeUnit.MILLISECONDS);

            return null;
        }).when(mqttClient).publish(eq(cmdTopic), any(MqttMessage.class));

        ActuatorCommandResponse res = gateway.executeCommand("pump", false, "docente");
        assertNotNull(res);
        assertTrue(res.ok());
        assertFalse(res.value());
        verify(auditService).recordCommand("docente", "pump", false, true, null);
    }

    @Test
    void testGetActuatorsStateWithFreshTelemetry() {
        when(telemetryProvider.isTelemetryFresh()).thenReturn(true);
        TelemetryFrame frame = new TelemetryFrame(
                1, 10L, 1000L,
                new TankTelemetry(1000.0, 25.0, 23.0),
                new TankTelemetry(500.0, 15.0, 23.0),
                1.5,
                Map.of("pump", true),
                Map.of("overflow_a", false),
                "auto"
        );
        when(telemetryProvider.getLatestTelemetry()).thenReturn(frame);

        Map<String, Boolean> state = gateway.getActuatorsState();
        assertNotNull(state);
        assertTrue(state.get("pump"));
    }

    @Test
    void testGetActuatorsStateWithStaleTelemetryReportsUnknown() {
        // Telemetría con más de 5 segundos de antigüedad (isTelemetryFresh=false)
        when(telemetryProvider.isTelemetryFresh()).thenReturn(false);
        TelemetryFrame staleFrame = new TelemetryFrame(
                1, 1L, 1000L,
                new TankTelemetry(1000.0, 25.0, 23.0),
                new TankTelemetry(500.0, 15.0, 23.0),
                0.0,
                Map.of("pump", false),
                Map.of("overflow_a", false),
                "auto"
        );
        when(telemetryProvider.getLatestTelemetry()).thenReturn(staleFrame);

        Map<String, Boolean> state = gateway.getActuatorsState();
        assertNotNull(state);
        // Debe reportar null (desconocido) y NUNCA asumir false (apagada)
        assertNull(state.get("pump"));
    }

    @Test
    void testInvalidTargetThrowsActuatorNotFoundException() {
        assertThrows(ActuatorNotFoundException.class, () ->
                gateway.executeCommand("valvula_inexistente", true, "docente")
        );
        verify(auditService).recordCommand("docente", "valvula_inexistente", true, false, "target_not_found");
    }

    @Test
    void testSendCommand_TurnOnWithStaleTelemetry_ThrowsInterlockViolationException() throws Exception {
        when(telemetryProvider.isTelemetryFresh()).thenReturn(false);

        InterlockViolationException ex = assertThrows(InterlockViolationException.class, () ->
                gateway.executeCommand("pump", true, "docente")
        );

        assertEquals("pump", ex.getTarget());
        assertTrue(ex.isRequestedValue());
        assertEquals("telemetry_stale", ex.getReason());
        assertTrue(ex.getMessage().contains("telemetría está desactualizada"));

        // Se audita el rechazo con reason="telemetry_stale"
        verify(auditService).recordCommand("docente", "pump", true, false, "telemetry_stale");
        // No se publica ningún mensaje en MQTT
        verify(mqttClient, never()).publish(anyString(), any(MqttMessage.class));
    }

    @Test
    void testSendCommand_TurnOffWithStaleTelemetry_Allowed() throws Exception {
        // Apagar SIEMPRE está permitido aún con telemetría vieja
        when(telemetryProvider.isTelemetryFresh()).thenReturn(false);

        doAnswer(invocation -> {
            MqttMessage msg = invocation.getArgument(1);
            BridgeCommandMessage cmd = objectMapper.readValue(msg.getPayload(), BridgeCommandMessage.class);

            Executors.newSingleThreadScheduledExecutor().schedule(() -> {
                try {
                    String ackJson = "{\"ack\":\"" + cmd.id() + "\",\"ok\":true}";
                    gateway.messageArrived(ackTopic, new MqttMessage(ackJson.getBytes()));
                } catch (Exception ignored) {
                }
            }, 20, TimeUnit.MILLISECONDS);

            return null;
        }).when(mqttClient).publish(eq(cmdTopic), any(MqttMessage.class));

        ActuatorCommandResponse res = gateway.executeCommand("pump", false, "docente");

        assertNotNull(res);
        assertTrue(res.ok());
        assertFalse(res.value());
        verify(auditService).recordCommand("docente", "pump", false, true, null);
        verify(mqttClient).publish(eq(cmdTopic), any(MqttMessage.class));
    }
}
