package ar.edu.utn.frsf.tanques.gateway;

import ar.edu.utn.frsf.tanques.audit.AuditService;
import ar.edu.utn.frsf.tanques.dto.ActuatorCommandResponse;
import ar.edu.utn.frsf.tanques.exception.ActuatorNotFoundException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

@Component
@Profile("prod")
public class BridgeActuatorGateway implements ActuatorGateway {

    private static final Logger log = LoggerFactory.getLogger(BridgeActuatorGateway.class);

    private final AuditService auditService;
    private final Map<String, Boolean> actuatorsState = new ConcurrentHashMap<>();
    private final Set<String> supportedTargets = Collections.newSetFromMap(new ConcurrentHashMap<>());

    public BridgeActuatorGateway(AuditService auditService) {
        this.auditService = auditService;
        supportedTargets.add("pump");
        actuatorsState.put("pump", false);
    }

    @Override
    public ActuatorCommandResponse executeCommand(String target, boolean value, String username) {
        String normalized = target.trim().toLowerCase();
        if (!isValidTarget(normalized)) {
            auditService.recordCommand(username, normalized, value, false, "target_not_found");
            throw new ActuatorNotFoundException(normalized);
        }

        String ackId = "cmd_" + System.currentTimeMillis();

        // TODO: En Fase futura / producción, enviar comando serial o HTTP JSON a edge/bridge.py
        // Ejemplo de trama hacia bridge: {"id": ackId, "cmd": "set", "target": normalized, "value": value}
        // y aguardar respuesta {"ack": ackId, "ok": true|false, "reason": "..."}
        log.warn("[PROD TODO] BridgeActuatorGateway: comando simulado temporalmente en producción: target={}, valor={}", normalized, value);

        actuatorsState.put(normalized, value);
        auditService.recordCommand(username, normalized, value, true, null);

        return new ActuatorCommandResponse(ackId, true, null, normalized, value, Instant.now());
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
}
