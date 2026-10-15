package ar.edu.utn.frsf.tanques.dto;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Respuesta de autenticación con token JWT")
public record AuthResponse(
        @Schema(description = "Token JWT emitido")
        String token,

        @Schema(description = "Nombre de usuario autenticado", example = "docente")
        String username,

        @Schema(description = "Rol asignado", example = "DOCENTE")
        String role
) {
}
