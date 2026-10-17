package ar.edu.utn.frsf.tanques.controller;

import ar.edu.utn.frsf.tanques.auth.JwtService;
import ar.edu.utn.frsf.tanques.auth.UserRepository;
import ar.edu.utn.frsf.tanques.domain.User;
import ar.edu.utn.frsf.tanques.dto.AuthResponse;
import ar.edu.utn.frsf.tanques.dto.LoginRequest;
import ar.edu.utn.frsf.tanques.dto.UserResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
@Tag(name = "Autenticación", description = "Endpoints de login y perfil de usuario")
public class AuthController {

        private final AuthenticationManager authenticationManager;
        private final JwtService jwtService;
        private final UserRepository userRepository;

        public AuthController(AuthenticationManager authenticationManager, JwtService jwtService,
                        UserRepository userRepository) {
                this.authenticationManager = authenticationManager;
                this.jwtService = jwtService;
                this.userRepository = userRepository;
        }

        @PostMapping("/auth/login")
        @Operation(summary = "Iniciar sesión", description = "Autentica credenciales y genera un token JWT stateless con el rol correspondiente.")
        @ApiResponses({
                        @ApiResponse(responseCode = "200", description = "Autenticación exitosa"),
                        @ApiResponse(responseCode = "401", description = "Credenciales incorrectas")
        })
        public ResponseEntity<AuthResponse> login(@Valid @RequestBody LoginRequest request) {
                authenticationManager.authenticate(
                                new UsernamePasswordAuthenticationToken(request.username(), request.password()));

                User user = userRepository.findByUsername(request.username())
                                .orElseThrow(() -> new UsernameNotFoundException("Usuario no encontrado"));

                String token = jwtService.generateToken(user.getUsername(), user.getRole());

                return ResponseEntity.ok(new AuthResponse(token, user.getUsername(), user.getRole().name()));
        }

        @GetMapping("/me")
        @Operation(summary = "Obtener perfil actual", description = "Devuelve el usuario y rol del token JWT provisto en la cabecera Authorization.")
        @ApiResponses({
                        @ApiResponse(responseCode = "200", description = "Datos del usuario actual"),
                        @ApiResponse(responseCode = "401", description = "No autenticado")
        })
        public ResponseEntity<UserResponse> getCurrentUser(Authentication authentication) {
                String username = authentication.getName();
                String role = authentication.getAuthorities().stream()
                                .map(getAuthority -> getAuthority.getAuthority())
                                .map(auth -> auth.startsWith("ROLE_") ? auth.substring(5) : auth)
                                .findFirst()
                                .orElse("ALUMNO");

                return ResponseEntity.ok(new UserResponse(username, role));
        }
}
