package ar.edu.utn.frsf.tanques.dto;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Métricas instantáneas de un tanque")
public record TankTelemetry(
        @Schema(description = "Masa medida por celda de carga en gramos", example = "1250.5")
        double weight_g,

        @Schema(description = "Porcentaje de llenado útil (0.0 a 100.0 %)", example = "31.2")
        double level_pct,

        @Schema(description = "Temperatura registrada en grados Celsius", example = "23.4")
        double temp_c
) {
}
