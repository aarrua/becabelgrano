package ar.edu.utn.frsf.tanques.gateway;

import ar.edu.utn.frsf.tanques.audit.AuditService;
import ar.edu.utn.frsf.tanques.dto.ActuatorCommandResponse;
import ar.edu.utn.frsf.tanques.exception.ActuatorNotFoundException;
import ar.edu.utn.frsf.tanques.exception.InterlockViolationException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

@Component
@Profile("dev")
public class MockActuatorGateway implements ActuatorGateway {

    private static final Logger log = LoggerFactory.getLogger(MockActuatorGateway.class);

    private final AuditService auditService;

    // Mapa extensible de estado de actuadores
    private final Map<String, Boolean> actuatorsState = new ConcurrentHashMap<>();

    // Conjunto extensible de actuadores válidos soportados
    private final Set<String> supportedTargets = Collections.newSetFromMap(new ConcurrentHashMap<>());

    // Alarmas/interlocks simulados en memoria
    private final Map<String, Boolean> simulatedAlarms = new ConcurrentHashMap<>();

    public MockActuatorGateway(AuditService auditService) {
        this.auditService = auditService;
        // Registro inicial del actuador físico disponible actualmente
        supportedTargets.add("pump");
        actuatorsState.put("pump", false);

        simulatedAlarms.put("overflow_a", false);
        simulatedAlarms.put("overflow_b", false);
        simulatedAlarms.put("sensor_fault", false);
    }

    @Override
    public ActuatorCommandResponse executeCommand(String target, boolean value, String username) {
        String normalizedTarget = target.trim().toLowerCase();

        if (!isValidTarget(normalizedTarget)) {
            auditService.recordCommand(username, normalizedTarget, value, false, "target_not_found");
            throw new ActuatorNotFoundException(normalizedTarget);
        }

        String ackId = "cmd_" + System.currentTimeMillis();

        // Verificación de interlocks de seguridad (mismos que en edge/simulator.py)
        if ("pump".equals(normalizedTarget) && value) {
            if (Boolean.TRUE.equals(simulatedAlarms.get("overflow_a"))) {
                auditService.recordCommand(username, normalizedTarget, value, false, "overflow_a");
                throw new InterlockViolationException(normalizedTarget, value, "overflow_a");
            }
            if (Boolean.TRUE.equals(simulatedAlarms.get("overflow_b"))) {
                auditService.recordCommand(username, normalizedTarget, value, false, "overflow_b");
                throw new InterlockViolationException(normalizedTarget, value, "overflow_b");
            }
            if (Boolean.TRUE.equals(simulatedAlarms.get("sensor_fault"))) {
                auditService.recordCommand(username, normalizedTarget, value, false, "sensor_fault");
                throw new InterlockViolationException(normalizedTarget, value, "sensor_fault");
            }
        }

        actuatorsState.put(normalizedTarget, value);
        auditService.recordCommand(username, normalizedTarget, value, true, null);
        log.info("Comando aplicado exitosamente en mock: usuario='{}', target='{}', valor={}", username, normalizedTarget, value);

        return ActuatorCommandResponse.success(ackId, normalizedTarget, value);
    }

    @Override
    public Map<String, Boolean> getActuatorsState() {
        return Collections.unmodifiableMap(new HashMap<>(actuatorsState));
    }

    @Override
    public boolean isValidTarget(String target) {
        return target != null && supportedTargets.contains(target.trim().toLowerCase());
    }

    @Override
    public Set<String> getSupportedTargets() {
        return Collections.unmodifiableSet(supportedTargets);
    }

    // Métodos para soporte de simulación y testing
    public void registerTarget(String target, boolean initialState) {
        String normalized = target.trim().toLowerCase();
        supportedTargets.add(normalized);
        actuatorsState.put(normalized, initialState);
    }

    public void setSimulatedAlarm(String alarmName, boolean active) {
        simulatedAlarms.put(alarmName, active);
        if (active && ("overflow_a".equals(alarmName) || "overflow_b".equals(alarmName))) {
            // Si hay sobrellenado, el interlock físico apaga la bomba de emergencia
            actuatorsState.put("pump", false);
        }
    }

    public Map<String, Boolean> getSimulatedAlarms() {
        return Collections.unmodifiableMap(new HashMap<>(simulatedAlarms));
    }
}
