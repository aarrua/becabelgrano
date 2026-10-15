package ar.edu.utn.frsf.tanques.telemetry;

import ar.edu.utn.frsf.tanques.config.TankGeometryConfig;
import ar.edu.utn.frsf.tanques.dto.TankTelemetry;
import ar.edu.utn.frsf.tanques.dto.TelemetryFrame;
import ar.edu.utn.frsf.tanques.gateway.MockActuatorGateway;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

@Component
@Profile("dev")
public class MockTelemetryProvider implements TelemetryProvider {

    private final MockActuatorGateway actuatorGateway;
    private final TankGeometryConfig geometryConfig;
    private final AtomicLong seqCounter = new AtomicLong(1);
    private final long startTime = System.currentTimeMillis();

    // Estado simulado en memoria
    private double volA = 1200.0; // ml
    private double volB = 600.0;  // ml
    private double tempA = 23.5;
    private double tempB = 23.2;

    public MockTelemetryProvider(MockActuatorGateway actuatorGateway, TankGeometryConfig geometryConfig) {
        this.actuatorGateway = actuatorGateway;
        this.geometryConfig = geometryConfig;
    }

    @Override
    public synchronized TelemetryFrame getLatestTelemetry() {
        long seq = seqCounter.getAndIncrement();
        long uptimeMs = System.currentTimeMillis() - startTime;

        Map<String, Boolean> actuators = actuatorGateway.getActuatorsState();
        boolean pump = actuators.getOrDefault("pump", false);

        double maxVolA = geometryConfig.getTankA().getVolumeMaxMl();
        double maxVolB = geometryConfig.getTankB().getVolumeMaxMl();

        // Pequeño paso de física mock
        if (pump) {
            volA = Math.min(maxVolA, volA + 30.0);
            volB = Math.max(0.0, volB - 15.0);
        } else {
            volA = Math.max(0.0, volA - 10.0);
            volB = Math.min(maxVolB, volB + 8.0);
        }

        double levelPctA = Math.min(100.0, Math.max(0.0, (volA / maxVolA) * 100.0));
        double levelPctB = Math.min(100.0, Math.max(0.0, (volB / maxVolB) * 100.0));

        // Actualizar interlocks si sobrepasa 95%
        if (levelPctA >= 95.0) {
            actuatorGateway.setSimulatedAlarm("overflow_a", true);
        }
        if (levelPctB >= 95.0) {
            actuatorGateway.setSimulatedAlarm("overflow_b", true);
        }

        double flowLpm = pump ? 2.2 : 0.0;

        TankTelemetry tankA = new TankTelemetry(
                Math.round(volA * 10.0) / 10.0,
                Math.round(levelPctA * 10.0) / 10.0,
                Math.round(tempA * 10.0) / 10.0
        );

        TankTelemetry tankB = new TankTelemetry(
                Math.round(volB * 10.0) / 10.0,
                Math.round(levelPctB * 10.0) / 10.0,
                Math.round(tempB * 10.0) / 10.0
        );

        Map<String, Boolean> alarms = new HashMap<>(actuatorGateway.getSimulatedAlarms());

        return new TelemetryFrame(
                1,
                seq,
                uptimeMs,
                tankA,
                tankB,
                flowLpm,
                actuators,
                alarms,
                "auto"
        );
    }
}
