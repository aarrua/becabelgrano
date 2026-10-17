package ar.edu.utn.frsf.tanques.telemetry;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class InfluxTelemetryProviderTest {

    @Test
    @DisplayName("Constructor falla con mensaje claro cuando falta INFLUX_URL")
    void constructorFailsWhenInfluxUrlIsMissingOrEmpty() {
        IllegalStateException exNull = assertThrows(IllegalStateException.class, () ->
                new InfluxTelemetryProvider(null, "some-token", "utn-frsf", "tanques")
        );
        assertTrue(exNull.getMessage().contains("INFLUX_URL"),
                "El mensaje debe indicar claramente que falta INFLUX_URL");

        IllegalStateException exBlank = assertThrows(IllegalStateException.class, () ->
                new InfluxTelemetryProvider("   ", "some-token", "utn-frsf", "tanques")
        );
        assertTrue(exBlank.getMessage().contains("INFLUX_URL"),
                "El mensaje debe indicar claramente que falta INFLUX_URL");
    }

    @Test
    @DisplayName("Constructor falla con mensaje claro cuando falta INFLUX_TOKEN")
    void constructorFailsWhenInfluxTokenIsMissingOrEmpty() {
        IllegalStateException exNull = assertThrows(IllegalStateException.class, () ->
                new InfluxTelemetryProvider("http://localhost:8086", null, "utn-frsf", "tanques")
        );
        assertTrue(exNull.getMessage().contains("INFLUX_TOKEN"),
                "El mensaje debe indicar claramente que falta INFLUX_TOKEN");

        IllegalStateException exBlank = assertThrows(IllegalStateException.class, () ->
                new InfluxTelemetryProvider("http://localhost:8086", "   ", "utn-frsf", "tanques")
        );
        assertTrue(exBlank.getMessage().contains("INFLUX_TOKEN"),
                "El mensaje debe indicar claramente que falta INFLUX_TOKEN");
    }

    @Test
    @DisplayName("Constructor inicializa cliente correctamente con URL y token válidos")
    void constructorSucceedsWithValidConfig() {
        assertDoesNotThrow(() -> {
            InfluxTelemetryProvider provider = new InfluxTelemetryProvider(
                    "http://localhost:8086",
                    "valid-test-token",
                    "utn-frsf",
                    "tanques"
            );
            provider.cleanup();
        });
    }
}
