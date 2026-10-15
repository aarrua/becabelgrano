package ar.edu.utn.frsf.tanques.exception;

public class ActuatorNotFoundException extends RuntimeException {

    private final String target;

    public ActuatorNotFoundException(String target) {
        super("El actuador '" + target + "' no existe o no es un target válido");
        this.target = target;
    }

    public String getTarget() {
        return target;
    }
}
