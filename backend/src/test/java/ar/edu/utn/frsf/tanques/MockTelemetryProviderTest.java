package ar.edu.utn.frsf.tanques;

import ar.edu.utn.frsf.tanques.audit.AuditService;
import ar.edu.utn.frsf.tanques.config.InterlockConfig;
import ar.edu.utn.frsf.tanques.config.TankGeometryConfig;
import ar.edu.utn.frsf.tanques.exception.InterlockViolationException;
import ar.edu.utn.frsf.tanques.gateway.MockActuatorGateway;
import ar.edu.utn.frsf.tanques.telemetry.MockTelemetryProvider;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
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

    @Test
    void overflowFlagMustHoldBetweenRearmAndThresholdAndRejectPump() {
        AuditService auditService = mock(AuditService.class);
        MockActuatorGateway gateway = new MockActuatorGateway(auditService);
        TankGeometryConfig geometryConfig = new TankGeometryConfig();
        InterlockConfig interlockConfig = new InterlockConfig();
        interlockConfig.setOverflowThresholdPct(85.0);
        interlockConfig.setOverflowRearmPct(80.0);
        MockTelemetryProvider provider = new MockTelemetryProvider(gateway, geometryConfig, interlockConfig);
        double maxB = geometryConfig.getTankB().getVolumeMaxMl();

        // Con la bomba apagada el tanque B drena apenas en dt=0, el nivel queda fijo
        provider.setVolumes(0.0, maxB * 0.86);
        provider.stepPhysics(0.0);
        assertTrue(gateway.getSimulatedAlarms().get("overflow_b"));

        // Entre 80 y 85 % la bandera se mantiene y el encendido se rechaza
        provider.setVolumes(0.0, maxB * 0.82);
        provider.stepPhysics(0.0);
        assertTrue(gateway.getSimulatedAlarms().get("overflow_b"));
        assertThrows(InterlockViolationException.class,
                () -> gateway.executeCommand("pump", true, "docente"));

        // Bajo 80 % se rearma
        provider.setVolumes(0.0, maxB * 0.79);
        provider.stepPhysics(0.0);
        assertFalse(gateway.getSimulatedAlarms().get("overflow_b"));

        // Subiendo, entre 80 y 85 % no se activa hasta alcanzar el umbral
        provider.setVolumes(0.0, maxB * 0.83);
        provider.stepPhysics(0.0);
        assertFalse(gateway.getSimulatedAlarms().get("overflow_b"));
    }
}
