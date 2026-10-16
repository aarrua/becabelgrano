package ar.edu.utn.frsf.tanques.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import java.time.Instant;

@Schema(description = "Resultado de la ejecución del comando sobre el actuador")
public record ActuatorCommandResponse(
        @Schema(description = "Identificador o acuse de comando", example = "cmd_1728950000000")
        String ack,

        @Schema(description = "Indica si el comando fue aceptado y aplicado", example = "true")
        boolean ok,

        @Schema(description = "Motivo de rechazo en caso de falla o disparo de interlock", example = "overflow_a")
        String reason,

        @Schema(description = "Actuador objetivo", example = "pump")
        String target,

        @Schema(description = "Valor aplicado o solicitado", example = "true")
        Boolean value,

        @Schema(description = "Timestamp oficial del procesamiento")
        Instant timestamp,

        @Schema(description = "Mensaje informativo o de diagnóstico sobre el estado del comando", example = "Estado desconocido, verificar telemetría")
        String message
) {
    public ActuatorCommandResponse(String ack, boolean ok, String reason, String target, Boolean value, Instant timestamp) {
        this(ack, ok, reason, target, value, timestamp, null);
    }

    public static ActuatorCommandResponse success(String ack, String target, boolean value) {
        return new ActuatorCommandResponse(ack, true, null, target, value, Instant.now(), null);
    }

    public static ActuatorCommandResponse rejected(String ack, String target, boolean value, String reason) {
        return new ActuatorCommandResponse(ack, false, reason, target, value, Instant.now(), null);
    }

    public static ActuatorCommandResponse rejected(String ack, String target, boolean value, String reason, String message) {
        return new ActuatorCommandResponse(ack, false, reason, target, value, Instant.now(), message);
    }
}
