package ar.edu.utn.frsf.tanques.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import java.time.Instant;

@Schema(description = "Registro de auditoría de comando")
public record AuditLogResponse(
        @Schema(description = "Identificador secuencial del evento", example = "1")
        Long id,

        @Schema(description = "Usuario que ejecutó el comando", example = "docente")
        String username,

        @Schema(description = "Actuador objetivo", example = "pump")
        String target,

        @Schema(description = "Valor solicitado", example = "true")
        boolean requestedValue,

        @Schema(description = "Resultado del comando (true si fue aceptado)", example = "true")
        boolean ok,

        @Schema(description = "Motivo de rechazo en caso de falla o interlock", example = "overflow_a")
        String reason,

        @Schema(description = "Timestamp en que se registró el evento")
        Instant timestamp
) {
}
