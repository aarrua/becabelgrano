package ar.edu.utn.frsf.tanques.telemetry;

import ar.edu.utn.frsf.tanques.config.InterlockConfig;
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
    private final InterlockConfig interlockConfig;
    private final AtomicLong seqCounter = new AtomicLong(1);
    private final long startTime = System.currentTimeMillis();

    // Estado simulado en memoria
    private double volA; // ml
    private double volB; // ml
    private double tempA = 23.5;
    private double tempB = 23.2;

    public MockTelemetryProvider(
            MockActuatorGateway actuatorGateway,
            TankGeometryConfig geometryConfig,
            InterlockConfig interlockConfig
    ) {
        this.actuatorGateway = actuatorGateway;
        this.geometryConfig = geometryConfig;
        this.interlockConfig = interlockConfig;

        // Niveles iniciales nominales (15% en A, 10% en B)
        this.volA = geometryConfig.getTankA().getVolumeMaxMl() * 0.15;
        this.volB = geometryConfig.getTankB().getVolumeMaxMl() * 0.10;
    }

    public synchronized void stepPhysics(double dt) {
        Map<String, Boolean> actuators = actuatorGateway.getActuatorsState();
        boolean pump = actuators.getOrDefault("pump", false);

        double maxVolA = geometryConfig.getTankA().getVolumeMaxMl();
        double maxVolB = geometryConfig.getTankB().getVolumeMaxMl();
        double areaA = geometryConfig.getTankA().getAreaCm2();
        double areaB = geometryConfig.getTankB().getAreaCm2();

        // 1. Caudal de entrada Bomba -> Tanque A (ml/s)
        double qInA = pump ? (2.2 * 1000.0 / 60.0) : 0.0;

        // 2. Caudal de salida Tanque A -> Tanque B (Torricelli)
        double hA = volA / areaA;
        double qOutA = (hA > 0.05) ? 0.045 * areaA * Math.sqrt(2.0 * 981.0 * hA) * 0.02 : 0.0;

        // 3. Caudal de salida Tanque B -> Reservorio (Torricelli)
        double hB = volB / areaB;
        double qOutB = (hB > 0.05) ? 0.038 * areaB * Math.sqrt(2.0 * 981.0 * hB) * 0.02 : 0.0;

        // Integración de volúmenes (Euler explícito)
        volA = Math.max(0.0, Math.min(maxVolA * 1.05, volA + (qInA - qOutA) * dt));
        volB = Math.max(0.0, Math.min(maxVolB * 1.05, volB + (qOutA - qOutB) * dt));

        double levelPctA = (volA / maxVolA) * 100.0;
        double levelPctB = (volB / maxVolB) * 100.0;

        // Evaluación de interlocks con histéresis (corte default 85%, rearme bajo 80%)
        Map<String, Boolean> alarms = actuatorGateway.getSimulatedAlarms();
        actuatorGateway.setSimulatedAlarm("overflow_a",
                nextOverflowState(alarms.get("overflow_a"), levelPctA));
        actuatorGateway.setSimulatedAlarm("overflow_b",
                nextOverflowState(alarms.get("overflow_b"), levelPctB));
    }

    /**
     * Se activa al llegar al umbral y solo se desactiva bajo el nivel de rearme; entre ambos
     * conserva el estado previo. Un nivel inválido (NaN) deja la bandera activa.
     */
    private boolean nextOverflowState(Boolean active, double levelPct) {
        double threshold = interlockConfig.getOverflowThresholdPct();
        double rearm = Math.min(interlockConfig.getOverflowRearmPct(), threshold);
        if (Double.isNaN(levelPct) || levelPct >= threshold) {
            return true;
        }
        if (levelPct < rearm) {
            return false;
        }
        return Boolean.TRUE.equals(active);
    }

    @Override
    public synchronized TelemetryFrame getLatestTelemetry() {
        stepPhysics(1.0);

        long seq = seqCounter.getAndIncrement();
        long uptimeMs = System.currentTimeMillis() - startTime;

        Map<String, Boolean> actuators = actuatorGateway.getActuatorsState();
        boolean pump = actuators.getOrDefault("pump", false);

        double maxVolA = geometryConfig.getTankA().getVolumeMaxMl();
        double maxVolB = geometryConfig.getTankB().getVolumeMaxMl();
        double levelPctA = Math.min(100.0, Math.max(0.0, (volA / maxVolA) * 100.0));
        double levelPctB = Math.min(100.0, Math.max(0.0, (volB / maxVolB) * 100.0));

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

    public synchronized double getLevelPctA() {
        return (volA / geometryConfig.getTankA().getVolumeMaxMl()) * 100.0;
    }

    public synchronized double getLevelPctB() {
        return (volB / geometryConfig.getTankB().getVolumeMaxMl()) * 100.0;
    }

    public synchronized void setVolumes(double volA, double volB) {
        this.volA = volA;
        this.volB = volB;
    }
}
