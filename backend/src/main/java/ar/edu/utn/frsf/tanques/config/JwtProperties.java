package ar.edu.utn.frsf.tanques.config;

import jakarta.annotation.PostConstruct;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "tanques.jwt")
public class JwtProperties {

    private String secret;
    private long expirationMs = 86400000L; // 24 horas

    @PostConstruct
    public void validate() {
        if (secret == null || secret.trim().length() < 32) {
            throw new IllegalStateException("El secreto JWT (tanques.jwt.secret) debe estar configurado y tener al menos 32 caracteres (256 bits).");
        }
    }

    public String getSecret() {
        return secret;
    }

    public void setSecret(String secret) {
        this.secret = secret;
    }

    public long getExpirationMs() {
        return expirationMs;
    }

    public void setExpirationMs(long expirationMs) {
        this.expirationMs = expirationMs;
    }
}
