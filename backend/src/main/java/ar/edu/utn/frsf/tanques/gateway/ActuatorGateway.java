package ar.edu.utn.frsf.tanques.gateway;

import ar.edu.utn.frsf.tanques.dto.ActuatorCommandResponse;

import java.util.Map;
import java.util.Set;

public interface ActuatorGateway {

    ActuatorCommandResponse executeCommand(String target, boolean value, String username);

    Map<String, Boolean> getActuatorsState();

    boolean isValidTarget(String target);

    Set<String> getSupportedTargets();
}
