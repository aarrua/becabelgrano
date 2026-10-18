package ar.edu.utn.frsf.tanques.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

@Schema(description = "Credenciales de autenticación")
public record LoginRequest(
        @Schema(description = "Nombre de usuario", example = "<usuario>")
        @NotBlank(message = "El nombre de usuario es obligatorio")
        String username,

        @Schema(description = "Contraseña", example = "<clave>")
        @NotBlank(message = "La contraseña es obligatoria")
        String password
) {
}
