package ar.edu.utn.frsf.tanques.gateway;

import ar.edu.utn.frsf.tanques.audit.AuditService;
import ar.edu.utn.frsf.tanques.dto.ActuatorCommandResponse;
import ar.edu.utn.frsf.tanques.dto.TelemetryFrame;
import ar.edu.utn.frsf.tanques.exception.ActuatorNotFoundException;
import ar.edu.utn.frsf.tanques.exception.BridgeUnavailableException;
import ar.edu.utn.frsf.tanques.telemetry.TelemetryProvider;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

@Component
@Profile("prod")
public class BridgeActuatorGateway implements ActuatorGateway {

    private static final Logger log = LoggerFactory.getLogger(BridgeActuatorGateway.class);

    private final AuditService auditService;
    private final ObjectProvider<TelemetryProvider> telemetryProvider;
    private final Set<String> supportedTargets = Collections.newSetFromMap(new ConcurrentHashMap<>());

    public BridgeActuatorGateway(AuditService auditService, ObjectProvider<TelemetryProvider> telemetryProvider) {
        this.auditService = auditService;
        this.telemetryProvider = telemetryProvider;
        supportedTargets.add("pump");
    }

    @Override
    public ActuatorCommandResponse executeCommand(String target, boolean value, String username) {
        String normalized = target.trim().toLowerCase();
        if (!isValidTarget(normalized)) {
            auditService.recordCommand(username, normalized, value, false, "target_not_found");
            throw new ActuatorNotFoundException(normalized);
        }

        // Mientras no exista el canal real hacia el bridge en edge/bridge.py,
        // no simular éxito: auditar el intento como rechazado y responder 503 Service Unavailable.
        auditService.recordCommand(username, normalized, value, false, "bridge_unavailable");
        log.warn("Comando sobre actuador '{}' rechazado: canal hacia bridge no disponible", normalized);

        throw new BridgeUnavailableException(normalized, value, "bridge_unavailable");
    }

    @Override
    public Map<String, Boolean> getActuatorsState() {
        // En producción el estado real de los actuadores se obtiene de la última telemetría
        TelemetryProvider provider = telemetryProvider.getIfAvailable();
        if (provider != null) {
            try {
                TelemetryFrame frame = provider.getLatestTelemetry();
                if (frame != null && frame.actuators() != null) {
                    return frame.actuators();
                }
            } catch (Exception e) {
                log.warn("No se pudo obtener el estado de actuadores desde la telemetría: {}", e.getMessage());
            }
        }
        return Collections.emptyMap();
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
