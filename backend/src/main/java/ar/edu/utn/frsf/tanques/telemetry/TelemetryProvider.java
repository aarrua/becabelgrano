package ar.edu.utn.frsf.tanques.telemetry;

import ar.edu.utn.frsf.tanques.dto.TelemetryFrame;

public interface TelemetryProvider {

    TelemetryFrame getLatestTelemetry();

    default boolean isTelemetryFresh() {
        return true;
    }
}
