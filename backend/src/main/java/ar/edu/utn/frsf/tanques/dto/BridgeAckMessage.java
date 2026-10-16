package ar.edu.utn.frsf.tanques.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import io.swagger.v3.oas.annotations.media.Schema;

@JsonIgnoreProperties(ignoreUnknown = true)
@Schema(description = "Respuesta de confirmación (ACK) recibida desde el Bridge/ESP32 por MQTT (tópico tanques/ack)")
public record BridgeAckMessage(
        @Schema(description = "Identificador de correlación asociado al comando original", example = "c_1a2b3c4d")
        String ack,

        @Schema(description = "Indica si el comando fue aceptado por el hardware", example = "true")
        boolean ok,

        @Schema(description = "Motivo de rechazo o falla en caso de ok=false", example = "overflow_a")
        String reason
) {
}
