package ar.edu.utn.frsf.tanques.exception;

import ar.edu.utn.frsf.tanques.dto.ActuatorCommandResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(InterlockViolationException.class)
    public ResponseEntity<ActuatorCommandResponse> handleInterlockViolation(InterlockViolationException ex) {
        log.warn("Comando rechazado por interlock de seguridad: target='{}', valor={}, motivo='{}'",
                ex.getTarget(), ex.isRequestedValue(), ex.getReason());
        String ackId = "cmd_" + UUID.randomUUID().toString().substring(0, 8);
        ActuatorCommandResponse response = ActuatorCommandResponse.rejected(
                ackId,
                ex.getTarget(),
                ex.isRequestedValue(),
                ex.getReason(),
                ex.getMessage()
        );
        return ResponseEntity.status(HttpStatus.CONFLICT).body(response);
    }

    @ExceptionHandler(BridgeUnavailableException.class)
    public ResponseEntity<ActuatorCommandResponse> handleBridgeUnavailable(BridgeUnavailableException ex) {
        log.warn("Comando rechazado por puente no disponible o timeout: target='{}', valor={}, motivo='{}', detalle='{}'",
                ex.getTarget(), ex.isRequestedValue(), ex.getReason(), ex.getMessage());
        String ackId = ex.getAckId() != null ? ex.getAckId() : "cmd_" + UUID.randomUUID().toString().substring(0, 8);
        ActuatorCommandResponse response = ActuatorCommandResponse.rejected(
                ackId,
                ex.getTarget(),
                ex.isRequestedValue(),
                ex.getReason(),
                ex.getMessage()
        );
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(response);
    }

    @ExceptionHandler(ActuatorNotFoundException.class)
    public ResponseEntity<Map<String, Object>> handleActuatorNotFound(ActuatorNotFoundException ex) {
        log.warn("Actuador no encontrado: {}", ex.getMessage());
        Map<String, Object> body = buildErrorBody(HttpStatus.NOT_FOUND, ex.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(body);
    }

    @ExceptionHandler(AuthenticationException.class)
    public ResponseEntity<Map<String, Object>> handleAuthenticationException(AuthenticationException ex) {
        log.warn("Falla de autenticación: {}", ex.getMessage());
        Map<String, Object> body = buildErrorBody(HttpStatus.UNAUTHORIZED, "Credenciales inválidas o token no autorizado");
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(body);
    }

    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<Map<String, Object>> handleAccessDenied(AccessDeniedException ex) {
        log.warn("Acceso denegado: {}", ex.getMessage());
        Map<String, Object> body = buildErrorBody(HttpStatus.FORBIDDEN, "No posee los permisos suficientes (requiere rol docente)");
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(body);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidationExceptions(MethodArgumentNotValidException ex) {
        Map<String, String> errors = new HashMap<>();
        for (FieldError error : ex.getBindingResult().getFieldErrors()) {
            errors.put(error.getField(), error.getDefaultMessage());
        }
        Map<String, Object> body = buildErrorBody(HttpStatus.BAD_REQUEST, "Error de validación en la petición");
        body.put("errors", errors);
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(body);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> handleIllegalArgument(IllegalArgumentException ex) {
        Map<String, Object> body = buildErrorBody(HttpStatus.BAD_REQUEST, ex.getMessage());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(body);
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> handleGeneralException(Exception ex) {
        log.error("Error interno no controlado: ", ex);
        Map<String, Object> body = buildErrorBody(HttpStatus.INTERNAL_SERVER_ERROR, "Error interno del servidor");
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(body);
    }

    private Map<String, Object> buildErrorBody(HttpStatus status, String message) {
        Map<String, Object> body = new HashMap<>();
        body.put("timestamp", Instant.now().toString());
        body.put("status", status.value());
        body.put("error", status.getReasonPhrase());
        body.put("message", message);
        return body;
    }
}
