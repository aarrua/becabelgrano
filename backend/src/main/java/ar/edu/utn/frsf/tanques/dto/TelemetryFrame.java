package ar.edu.utn.frsf.tanques.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import java.util.Map;

@Schema(description = "Trama completa de telemetría del kit didáctico (Contrato JSON v1)")
public record TelemetryFrame(
        @Schema(description = "Versión del protocolo", example = "1")
        int v,

        @Schema(description = "Secuencia incremental de trama", example = "1042")
        long seq,

        @Schema(description = "Tiempo de actividad en milisegundos", example = "523411")
        long uptime_ms,

        @Schema(description = "Estado del Tanque A (Superior)")
        TankTelemetry tank_a,

        @Schema(description = "Estado del Tanque B (Inferior)")
        TankTelemetry tank_b,

        @Schema(description = "Caudal medido en litros por minuto (L/min)", example = "1.8")
        double flow_lpm,

        @Schema(description = "Mapa de estado de actuadores físicos")
        Map<String, Boolean> actuators,

        @Schema(description = "Mapa de alarmas e interlocks activos")
        Map<String, Boolean> alarms,

        @Schema(description = "Modo de control del sistema", example = "auto")
        String mode
) {
}
