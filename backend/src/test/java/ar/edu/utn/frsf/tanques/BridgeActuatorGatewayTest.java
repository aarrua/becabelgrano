package ar.edu.utn.frsf.tanques;

import ar.edu.utn.frsf.tanques.audit.AuditService;
import ar.edu.utn.frsf.tanques.dto.TankTelemetry;
import ar.edu.utn.frsf.tanques.dto.TelemetryFrame;
import ar.edu.utn.frsf.tanques.exception.BridgeUnavailableException;
import ar.edu.utn.frsf.tanques.gateway.BridgeActuatorGateway;
import ar.edu.utn.frsf.tanques.telemetry.TelemetryProvider;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class BridgeActuatorGatewayTest {

    @Test
    void executeCommandShouldAuditRejectionAndThrowBridgeUnavailableException() {
        AuditService auditService = mock(AuditService.class);
        @SuppressWarnings("unchecked")
        ObjectProvider<TelemetryProvider> provider = mock(ObjectProvider.class);

        BridgeActuatorGateway gateway = new BridgeActuatorGateway(auditService, provider);

        BridgeUnavailableException ex = assertThrows(BridgeUnavailableException.class, () ->
                gateway.executeCommand("pump", true, "docente")
        );

        assertEquals("pump", ex.getTarget());
        assertTrue(ex.isRequestedValue());
        assertEquals("bridge_unavailable", ex.getReason());

        verify(auditService).recordCommand("docente", "pump", true, false, "bridge_unavailable");
    }

    @Test
    void getActuatorsStateShouldReadFromTelemetryProvider() {
        AuditService auditService = mock(AuditService.class);
        @SuppressWarnings("unchecked")
        ObjectProvider<TelemetryProvider> objectProvider = mock(ObjectProvider.class);
        TelemetryProvider telemetryProvider = mock(TelemetryProvider.class);

        when(objectProvider.getIfAvailable()).thenReturn(telemetryProvider);

        TelemetryFrame frame = new TelemetryFrame(
                1,
                10L,
                1000L,
                new TankTelemetry(1200.0, 30.0, 23.5),
                new TankTelemetry(600.0, 24.0, 23.2),
                0.0,
                Map.of("pump", true),
                Map.of("overflow_a", false),
                "auto"
        );
        when(telemetryProvider.getLatestTelemetry()).thenReturn(frame);

        BridgeActuatorGateway gateway = new BridgeActuatorGateway(auditService, objectProvider);
        Map<String, Boolean> state = gateway.getActuatorsState();

        assertEquals(1, state.size());
        assertTrue(state.get("pump"));
    }
}
