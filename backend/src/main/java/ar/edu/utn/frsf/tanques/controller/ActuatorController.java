package ar.edu.utn.frsf.tanques.controller;

import ar.edu.utn.frsf.tanques.dto.ActuatorCommandRequest;
import ar.edu.utn.frsf.tanques.dto.ActuatorCommandResponse;
import ar.edu.utn.frsf.tanques.gateway.ActuatorGateway;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/actuators")
@Tag(name = "Actuadores", description = "Monitoreo y control de actuadores físicos")
public class ActuatorController {

    private final ActuatorGateway actuatorGateway;

    public ActuatorController(ActuatorGateway actuatorGateway) {
        this.actuatorGateway = actuatorGateway;
    }

    @GetMapping
    @Operation(summary = "Consultar actuadores", description = "Devuelve el mapa con el estado actual de todos los actuadores físicos.")
    @ApiResponses({
            @ApiResponse(responseCode = "200", description = "Mapa de actuadores"),
            @ApiResponse(responseCode = "401", description = "No autenticado")
    })
    public ResponseEntity<Map<String, Boolean>> getActuators() {
        return ResponseEntity.ok(actuatorGateway.getActuatorsState());
    }

    @PostMapping("/{name}")
    @PreAuthorize("hasRole('DOCENTE')")
    @Operation(summary = "Comandar actuador", description = "Permite alterar el estado de un actuador físico. Exclusivo para usuarios con rol DOCENTE.")
    @ApiResponses({
            @ApiResponse(responseCode = "200", description = "Comando aceptado y aplicado"),
            @ApiResponse(responseCode = "401", description = "No autenticado"),
            @ApiResponse(responseCode = "403", description = "Acceso denegado (requiere rol DOCENTE)"),
            @ApiResponse(responseCode = "404", description = "Actuador no encontrado"),
            @ApiResponse(responseCode = "409", description = "Comando rechazado por interlock de seguridad (incluye reason)")
    })
    public ResponseEntity<ActuatorCommandResponse> setActuatorState(
            @PathVariable String name,
            @Valid @RequestBody ActuatorCommandRequest request,
            Authentication authentication
    ) {
        String username = authentication != null ? authentication.getName() : "anonymous";
        ActuatorCommandResponse response = actuatorGateway.executeCommand(name, request.value(), username);
        return ResponseEntity.ok(response);
    }
}
