package ar.edu.utn.frsf.tanques;

import ar.edu.utn.frsf.tanques.audit.AuditService;
import ar.edu.utn.frsf.tanques.config.InterlockConfig;
import ar.edu.utn.frsf.tanques.config.TankGeometryConfig;
import ar.edu.utn.frsf.tanques.gateway.MockActuatorGateway;
import ar.edu.utn.frsf.tanques.telemetry.MockTelemetryProvider;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;

class MockTelemetryProviderTest {

    @Test
    void fullPumpingCycleWith85PctThresholdMustKeepBothTanksBelow99Pct() {
        AuditService auditService = mock(AuditService.class);
        MockActuatorGateway gateway = new MockActuatorGateway(auditService);
        TankGeometryConfig geometryConfig = new TankGeometryConfig();
        InterlockConfig interlockConfig = new InterlockConfig();
        interlockConfig.setOverflowThresholdPct(85.0);

        MockTelemetryProvider provider = new MockTelemetryProvider(gateway, geometryConfig, interlockConfig);

        // Encender la bomba
        gateway.executeCommand("pump", true, "docente");
        assertTrue(gateway.getActuatorsState().get("pump"));

        double maxA = 0.0;
        double maxB = 0.0;

        // Correr ciclo completo de 5000 pasos de 0.1s (500 segundos simulados)
        for (int i = 0; i < 5000; i++) {
            provider.stepPhysics(0.1);

            double pctA = provider.getLevelPctA();
            double pctB = provider.getLevelPctB();

            if (pctA > maxA) maxA = pctA;
            if (pctB > maxB) maxB = pctB;
        }

        // El interlock debe haber disparado y apagado la bomba
        assertFalse(gateway.getActuatorsState().get("pump"), "La bomba debió haberse apagado por interlock");

        // Ningún tanque debe haber superado el 99%
        assertTrue(maxA < 99.0, "Tanque A superó el 99%: " + maxA);
        assertTrue(maxB < 99.0, "Tanque B superó el 99%: " + maxB);
    }
}
