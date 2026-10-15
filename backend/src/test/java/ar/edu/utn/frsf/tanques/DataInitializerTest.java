package ar.edu.utn.frsf.tanques;

import ar.edu.utn.frsf.tanques.auth.DataInitializer;
import ar.edu.utn.frsf.tanques.auth.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;

class DataInitializerTest {

    @Test
    void validateShouldThrowIfDocentePasswordMissingOrBlank() {
        UserRepository repo = mock(UserRepository.class);
        PasswordEncoder encoder = mock(PasswordEncoder.class);
        DataInitializer initializer = new DataInitializer(repo, encoder);

        ReflectionTestUtils.setField(initializer, "defaultDocentePassword", "");
        ReflectionTestUtils.setField(initializer, "defaultAlumnoPassword", "alumno123");

        assertThrows(IllegalStateException.class, initializer::validate);
    }

    @Test
    void validateShouldThrowIfAlumnoPasswordMissingOrBlank() {
        UserRepository repo = mock(UserRepository.class);
        PasswordEncoder encoder = mock(PasswordEncoder.class);
        DataInitializer initializer = new DataInitializer(repo, encoder);

        ReflectionTestUtils.setField(initializer, "defaultDocentePassword", "docente123");
        ReflectionTestUtils.setField(initializer, "defaultAlumnoPassword", "   ");

        assertThrows(IllegalStateException.class, initializer::validate);
    }
}
