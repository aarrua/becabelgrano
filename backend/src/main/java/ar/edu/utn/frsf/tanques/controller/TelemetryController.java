package ar.edu.utn.frsf.tanques.controller;

import ar.edu.utn.frsf.tanques.dto.TelemetryFrame;
import ar.edu.utn.frsf.tanques.telemetry.TelemetryProvider;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/telemetry")
@Tag(name = "Telemetría", description = "Lectura del estado instantáneo de la planta de tanques")
public class TelemetryController {

    private final TelemetryProvider telemetryProvider;

    public TelemetryController(TelemetryProvider telemetryProvider) {
        this.telemetryProvider = telemetryProvider;
    }

    @GetMapping("/latest")
    @Operation(summary = "Obtener última telemetría", description = "Devuelve la trama instantánea más reciente del kit didáctico cumpliendo el esquema del contrato JSON.")
    @ApiResponses({
            @ApiResponse(responseCode = "200", description = "Telemetría obtenida con éxito"),
            @ApiResponse(responseCode = "401", description = "No autenticado")
    })
    public ResponseEntity<TelemetryFrame> getLatestTelemetry() {
        TelemetryFrame frame = telemetryProvider.getLatestTelemetry();
        return ResponseEntity.ok(frame);
    }
}
