package ar.edu.utn.frsf.tanques.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "command_audit_events")
public class CommandAuditEvent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 64)
    private String username;

    @Column(nullable = false, length = 64)
    private String target;

    @Column(nullable = false)
    private boolean requestedValue;

    @Column(nullable = false)
    private boolean ok;

    @Column(length = 128)
    private String reason;

    @Column(nullable = false)
    private Instant timestamp;

    public CommandAuditEvent() {
    }

    public CommandAuditEvent(String username, String target, boolean requestedValue, boolean ok, String reason) {
        this.username = username;
        this.target = target;
        this.requestedValue = requestedValue;
        this.ok = ok;
        this.reason = reason;
        this.timestamp = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getTarget() {
        return target;
    }

    public void setTarget(String target) {
        this.target = target;
    }

    public boolean isRequestedValue() {
        return requestedValue;
    }

    public void setRequestedValue(boolean requestedValue) {
        this.requestedValue = requestedValue;
    }

    public boolean isOk() {
        return ok;
    }

    public void setOk(boolean ok) {
        this.ok = ok;
    }

    public String getReason() {
        return reason;
    }

    public void setReason(String reason) {
        this.reason = reason;
    }

    public Instant getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(Instant timestamp) {
        this.timestamp = timestamp;
    }
}
