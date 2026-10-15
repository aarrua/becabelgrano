package ar.edu.utn.frsf.tanques.exception;

public class InterlockViolationException extends RuntimeException {

    private final String reason;
    private final String target;
    private final boolean requestedValue;

    public InterlockViolationException(String target, boolean requestedValue, String reason) {
        super("Comando rechazado por interlock de seguridad (" + reason + ") en target '" + target + "'");
        this.target = target;
        this.requestedValue = requestedValue;
        this.reason = reason;
    }

    public String getReason() {
        return reason;
    }

    public String getTarget() {
        return target;
    }

    public boolean isRequestedValue() {
        return requestedValue;
    }
}
