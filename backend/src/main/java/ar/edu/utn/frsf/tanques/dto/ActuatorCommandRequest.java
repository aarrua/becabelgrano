package ar.edu.utn.frsf.tanques.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;

@Schema(description = "Petición para alterar el estado de un actuador")
public record ActuatorCommandRequest(
        @Schema(description = "Valor booleano deseado (true: encender, false: apagar)", example = "true")
        @NotNull(message = "El valor booleano 'value' es obligatorio")
        Boolean value
) {
}
