package ar.edu.utn.frsf.tanques;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Map;

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("dev")
class TelemetryControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void getTelemetryLatestWithoutTokenShouldReturn401() throws Exception {
        mockMvc.perform(get("/api/telemetry/latest"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void getTelemetryLatestWithAlumnoTokenShouldReturnContractPayload() throws Exception {
        String token = obtainToken("alumno", "alumno123");

        mockMvc.perform(get("/api/telemetry/latest")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.v", is(1)))
                .andExpect(jsonPath("$.seq", greaterThanOrEqualTo(1)))
                .andExpect(jsonPath("$.uptime_ms", greaterThanOrEqualTo(0)))
                .andExpect(jsonPath("$.tank_a.level_pct", notNullValue()))
                .andExpect(jsonPath("$.tank_a.weight_g", notNullValue()))
                .andExpect(jsonPath("$.tank_a.temp_c", notNullValue()))
                .andExpect(jsonPath("$.tank_b.level_pct", notNullValue()))
                .andExpect(jsonPath("$.actuators.pump", notNullValue()))
                .andExpect(jsonPath("$.alarms.overflow_a", notNullValue()))
                .andExpect(jsonPath("$.mode", is("auto")));
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
