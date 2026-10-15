package ar.edu.utn.frsf.tanques;

import ar.edu.utn.frsf.tanques.auth.JwtService;
import ar.edu.utn.frsf.tanques.config.JwtProperties;
import ar.edu.utn.frsf.tanques.domain.Role;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class JwtServiceTest {

    private JwtService jwtService;

    @BeforeEach
    void setUp() {
        JwtProperties properties = new JwtProperties();
        properties.setSecret("dev-secret-key-tanques-utn-frsf-gitda-2025-at-least-32-chars!");
        properties.setExpirationMs(3600000L);
        properties.validate();

        jwtService = new JwtService(properties);
    }

    @Test
    void shouldGenerateAndValidateTokenSuccessfully() {
        String token = jwtService.generateToken("docente", Role.DOCENTE);

        assertNotNull(token);
        assertTrue(jwtService.validateToken(token));
        assertEquals("docente", jwtService.extractUsername(token));
        assertEquals("DOCENTE", jwtService.extractRole(token));
    }

    @Test
    void shouldRejectInvalidOrTamperedToken() {
        String token = jwtService.generateToken("alumno", Role.ALUMNO);
        String tamperedToken = token + "corrupted";

        assertFalse(jwtService.validateToken(tamperedToken));
    }

    @Test
    void shouldThrowExceptionWhenSecretIsShorterThan32Characters() {
        JwtProperties properties = new JwtProperties();
        properties.setSecret("short-secret");
        assertThrows(IllegalStateException.class, properties::validate);
    }
}
