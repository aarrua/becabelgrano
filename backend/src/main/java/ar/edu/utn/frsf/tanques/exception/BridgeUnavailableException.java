package ar.edu.utn.frsf.tanques.exception;

public class BridgeUnavailableException extends RuntimeException {

    private final String target;
    private final boolean requestedValue;
    private final String reason;
    private final String ackId;

    public BridgeUnavailableException(String target, boolean requestedValue, String reason) {
        this(target, requestedValue, reason, "Canal hacia bridge no disponible (" + reason + ") para actuador '" + target + "'", null);
    }

    public BridgeUnavailableException(String target, boolean requestedValue, String reason, String message) {
        this(target, requestedValue, reason, message, null);
    }

    public BridgeUnavailableException(String target, boolean requestedValue, String reason, String message, String ackId) {
        super(message);
        this.target = target;
        this.requestedValue = requestedValue;
        this.reason = reason;
        this.ackId = ackId;
    }

    public String getTarget() {
        return target;
    }

    public boolean isRequestedValue() {
        return requestedValue;
    }

    public String getReason() {
        return reason;
    }

    public String getAckId() {
        return ackId;
    }
}
