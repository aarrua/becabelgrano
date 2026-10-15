package ar.edu.utn.frsf.tanques;

import ar.edu.utn.frsf.tanques.gateway.MockActuatorGateway;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Map;

import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("dev")
class ActuatorControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private MockActuatorGateway mockActuatorGateway;

    @BeforeEach
    void setUp() {
        // Reset de alarmas simuladas
        mockActuatorGateway.setSimulatedAlarm("overflow_a", false);
        mockActuatorGateway.setSimulatedAlarm("overflow_b", false);
        mockActuatorGateway.setSimulatedAlarm("sensor_fault", false);
    }

    @Test
    void getActuatorsWithoutTokenShouldReturn401() throws Exception {
        mockMvc.perform(get("/api/actuators"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void getActuatorsWithValidTokenShouldReturnActuatorMap() throws Exception {
        String token = obtainToken("alumno", "alumno123");

        mockMvc.perform(get("/api/actuators")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.pump", notNullValue()));
    }

    @Test
    void postActuatorWithAlumnoRoleShouldReturn403Forbidden() throws Exception {
        String alumnoToken = obtainToken("alumno", "alumno123");

        Map<String, Boolean> body = Map.of("value", true);

        mockMvc.perform(post("/api/actuators/pump")
                        .header("Authorization", "Bearer " + alumnoToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(body)))
                .andExpect(status().isForbidden());
    }

    @Test
    void postActuatorWithDocenteRoleShouldReturn200Ok() throws Exception {
        String docenteToken = obtainToken("docente", "docente123");

        Map<String, Boolean> body = Map.of("value", true);

        mockMvc.perform(post("/api/actuators/pump")
                        .header("Authorization", "Bearer " + docenteToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(body)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok", is(true)))
                .andExpect(jsonPath("$.target", is("pump")))
                .andExpect(jsonPath("$.value", is(true)));
    }

    @Test
    void postActuatorWithInterlockActiveShouldReturn409ConflictWithReason() throws Exception {
        String docenteToken = obtainToken("docente", "docente123");

        // Simular que el interlock de sobrellenado en Tanque A está activo (>95%)
        mockActuatorGateway.setSimulatedAlarm("overflow_a", true);

        Map<String, Boolean> body = Map.of("value", true);

        mockMvc.perform(post("/api/actuators/pump")
                        .header("Authorization", "Bearer " + docenteToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(body)))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.ok", is(false)))
                .andExpect(jsonPath("$.reason", is("overflow_a")))
                .andExpect(jsonPath("$.target", is("pump")))
                .andExpect(jsonPath("$.value", is(true)));
    }

    @Test
    void postInvalidActuatorShouldReturn404NotFound() throws Exception {
        String docenteToken = obtainToken("docente", "docente123");

        Map<String, Boolean> body = Map.of("value", true);

        mockMvc.perform(post("/api/actuators/valvula_inexistente")
                        .header("Authorization", "Bearer " + docenteToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(body)))
                .andExpect(status().isNotFound());
    }

    private String obtainToken(String username, String password) throws Exception {
        Map<String, String> loginRequest = Map.of(
                "username", username,
                "password", password
        );

        String response = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(loginRequest)))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();

        return objectMapper.readTree(response).get("token").asText();
    }
}
