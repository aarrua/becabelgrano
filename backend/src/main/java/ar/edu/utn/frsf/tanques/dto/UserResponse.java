package ar.edu.utn.frsf.tanques.dto;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Perfil del usuario autenticado actual")
public record UserResponse(
        @Schema(description = "Nombre de usuario", example = "docente")
        String username,

        @Schema(description = "Rol del usuario", example = "DOCENTE")
        String role
) {
}
