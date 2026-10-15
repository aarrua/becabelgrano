package ar.edu.utn.frsf.tanques.controller;

import ar.edu.utn.frsf.tanques.audit.AuditService;
import ar.edu.utn.frsf.tanques.dto.AuditLogResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/audit")
@Tag(name = "Auditoría", description = "Historial de comandos y eventos de control ejecutados")
public class AuditController {

    private final AuditService auditService;

    public AuditController(AuditService auditService) {
        this.auditService = auditService;
    }

    @GetMapping
    @PreAuthorize("hasRole('DOCENTE')")
    @Operation(summary = "Consultar registros de auditoría", description = "Obtiene la lista cronológica descendente de todos los comandos ejecutados. Exclusivo para rol DOCENTE.")
    @ApiResponses({
            @ApiResponse(responseCode = "200", description = "Lista de eventos de auditoría"),
            @ApiResponse(responseCode = "401", description = "No autenticado"),
            @ApiResponse(responseCode = "403", description = "Acceso denegado (requiere rol DOCENTE)")
    })
    public ResponseEntity<List<AuditLogResponse>> getAuditLogs() {
        return ResponseEntity.ok(auditService.getAllAuditLogs());
    }
}
