package ar.edu.utn.frsf.tanques.exception;

public class BridgeUnavailableException extends RuntimeException {

    private final String target;
    private final boolean requestedValue;
    private final String reason;

    public BridgeUnavailableException(String target, boolean requestedValue, String reason) {
        super("Canal hacia bridge no disponible (" + reason + ") para actuador '" + target + "'");
        this.target = target;
        this.requestedValue = requestedValue;
        this.reason = reason;
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
}
