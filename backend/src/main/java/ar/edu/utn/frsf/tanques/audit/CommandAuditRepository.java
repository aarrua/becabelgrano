package ar.edu.utn.frsf.tanques.audit;

import ar.edu.utn.frsf.tanques.domain.CommandAuditEvent;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface CommandAuditRepository extends JpaRepository<CommandAuditEvent, Long> {
    List<CommandAuditEvent> findAllByOrderByTimestampDesc();
}
