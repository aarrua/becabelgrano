package ar.edu.utn.frsf.tanques.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Métricas instantáneas de un tanque")
public record TankTelemetry(
        @JsonProperty("weight_g")
        @Schema(description = "Masa medida por celda de carga en gramos", example = "1250.5")
        Double weight_g,

        @JsonProperty("level_pct")
        @Schema(description = "Porcentaje de llenado útil (0.0 a 100.0 %)", example = "31.2")
        Double level_pct,

        @JsonProperty("temp_c")
        @Schema(description = "Temperatura registrada en grados Celsius", example = "23.4")
        Double temp_c
) {
}
