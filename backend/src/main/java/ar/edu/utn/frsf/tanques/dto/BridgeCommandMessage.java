package ar.edu.utn.frsf.tanques.dto;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Trama de comando enviada al Bridge/Equipo por MQTT (tópico tanques/cmd)")
public record BridgeCommandMessage(
        @Schema(description = "Identificador único de correlación", example = "c_1a2b3c4d")
        String id,

        @Schema(description = "Operación a ejecutar", example = "set")
        String cmd,

        @Schema(description = "Actuador objetivo", example = "pump")
        String target,

        @Schema(description = "Valor booleano solicitado", example = "true")
        boolean value,

        @Schema(description = "Timestamp epoch en milisegundos de emisión", example = "1792186882265")
        long ts
) {
    public static BridgeCommandMessage set(String id, String target, boolean value) {
        return new BridgeCommandMessage(id, "set", target, value, System.currentTimeMillis());
    }
}
