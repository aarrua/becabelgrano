package ar.edu.utn.frsf.tanques;

import ar.edu.utn.frsf.tanques.audit.AuditService;
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
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("dev")
class AuditControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private AuditService auditService;

    @Test
    void getAuditWithoutTokenShouldReturn401() throws Exception {
        mockMvc.perform(get("/api/audit"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void getAuditWithAlumnoRoleShouldReturn403Forbidden() throws Exception {
        String alumnoToken = obtainToken("alumno", "alumno123");

        mockMvc.perform(get("/api/audit")
                        .header("Authorization", "Bearer " + alumnoToken))
                .andExpect(status().isForbidden());
    }

    @Test
    void getAuditWithDocenteRoleShouldReturn200AndAuditList() throws Exception {
        // Registrar un evento previo
        auditService.recordCommand("docente", "pump", true, true, null);

        String docenteToken = obtainToken("docente", "docente123");

        mockMvc.perform(get("/api/audit")
                        .header("Authorization", "Bearer " + docenteToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", not(empty())))
                .andExpect(jsonPath("$[0].username", notNullValue()))
                .andExpect(jsonPath("$[0].target", notNullValue()));
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
