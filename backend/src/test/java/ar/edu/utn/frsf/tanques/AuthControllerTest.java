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
class AuthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void loginWithCorrectDocenteCredentialsShouldReturnTokenAndDocenteRole() throws Exception {
        Map<String, String> loginRequest = Map.of(
                "username", "docente",
                "password", "docente123"
        );

        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(loginRequest)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.token", not(emptyOrNullString())))
                .andExpect(jsonPath("$.username", is("docente")))
                .andExpect(jsonPath("$.role", is("DOCENTE")));
    }

    @Test
    void loginWithCorrectAlumnoCredentialsShouldReturnTokenAndAlumnoRole() throws Exception {
        Map<String, String> loginRequest = Map.of(
                "username", "alumno",
                "password", "alumno123"
        );

        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(loginRequest)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.token", not(emptyOrNullString())))
                .andExpect(jsonPath("$.username", is("alumno")))
                .andExpect(jsonPath("$.role", is("ALUMNO")));
    }

    @Test
    void loginWithIncorrectPasswordShouldReturn401Unauthorized() throws Exception {
        Map<String, String> loginRequest = Map.of(
                "username", "docente",
                "password", "wrongpassword"
        );

        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(loginRequest)))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.status", is(401)));
    }

    @Test
    void getMeWithoutTokenShouldReturn401Unauthorized() throws Exception {
        mockMvc.perform(get("/api/me"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void getMeWithValidDocenteTokenShouldReturnUserAndRole() throws Exception {
        String token = obtainToken("docente", "docente123");

        mockMvc.perform(get("/api/me")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.username", is("docente")))
                .andExpect(jsonPath("$.role", is("DOCENTE")));
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
