package ar.edu.utn.frsf.tanques.auth;

import ar.edu.utn.frsf.tanques.domain.Role;
import ar.edu.utn.frsf.tanques.domain.User;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

@Component
public class DataInitializer implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(DataInitializer.class);

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    @Value("${tanques.auth.default-docente-password:docente123}")
    private String defaultDocentePassword;

    @Value("${tanques.auth.default-alumno-password:alumno123}")
    private String defaultAlumnoPassword;

    public DataInitializer(UserRepository userRepository, PasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    public void run(String... args) {
        if (!userRepository.existsByUsername("docente")) {
            User docente = new User("docente", passwordEncoder.encode(defaultDocentePassword), Role.DOCENTE);
            userRepository.save(docente);
            log.info("Usuario semilla 'docente' creado exitosamente con rol DOCENTE.");
        }

        if (!userRepository.existsByUsername("alumno")) {
            User alumno = new User("alumno", passwordEncoder.encode(defaultAlumnoPassword), Role.ALUMNO);
            userRepository.save(alumno);
            log.info("Usuario semilla 'alumno' creado exitosamente con rol ALUMNO.");
        }
    }
}
