package ar.edu.utn.frsf.tanques.audit;

import ar.edu.utn.frsf.tanques.domain.CommandAuditEvent;
import ar.edu.utn.frsf.tanques.dto.AuditLogResponse;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class AuditService {

    private final CommandAuditRepository auditRepository;

    public AuditService(CommandAuditRepository auditRepository) {
        this.auditRepository = auditRepository;
    }

    @Transactional
    public CommandAuditEvent recordCommand(String username, String target, boolean requestedValue, boolean ok, String reason) {
        CommandAuditEvent event = new CommandAuditEvent(username, target, requestedValue, ok, reason);
        return auditRepository.save(event);
    }

    @Transactional(readOnly = true)
    public List<AuditLogResponse> getAllAuditLogs() {
        return auditRepository.findAllByOrderByTimestampDesc()
                .stream()
                .map(event -> new AuditLogResponse(
                        event.getId(),
                        event.getUsername(),
                        event.getTarget(),
                        event.isRequestedValue(),
                        event.isOk(),
                        event.getReason(),
                        event.getTimestamp()
                ))
                .toList();
    }
}
