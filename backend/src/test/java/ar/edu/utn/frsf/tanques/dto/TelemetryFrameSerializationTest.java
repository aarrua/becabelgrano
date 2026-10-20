package ar.edu.utn.frsf.tanques.dto;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class TelemetryFrameSerializationTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    @DisplayName("TelemetryFrame con niveles y temperaturas en null se serializa correctamente a JSON")
    void testSerializationWithNullSensorFields() throws Exception {
        TankTelemetry tankA = new TankTelemetry(null, null, null);
        TankTelemetry tankB = new TankTelemetry(null, null, null);
        TelemetryFrame frame = new TelemetryFrame(
                1,
                100L,
                12500L,
                tankA,
                tankB,
                null,
                Map.of("pump", false),
                Map.of("sensor_fault", true, "overflow_a", false, "overflow_b", false),
                "auto"
        );

        String json = objectMapper.writeValueAsString(frame);

        assertTrue(json.contains("\"tank_a\":{\"weight_g\":null,\"level_pct\":null,\"temp_c\":null}"));
        assertTrue(json.contains("\"tank_b\":{\"weight_g\":null,\"level_pct\":null,\"temp_c\":null}"));
        assertTrue(json.contains("\"flow_lpm\":null"));
        assertTrue(json.contains("\"seq\":100"));
        assertTrue(json.contains("\"pump\":false"));
        assertTrue(json.contains("\"sensor_fault\":true"));
    }

    @Test
    @DisplayName("TelemetryFrame deserializa correctamente JSON con campos nulos sin lanzar excepción")
    void testDeserializationWithNullSensorFields() throws Exception {
        String json = """
                {
                  "v": 1,
                  "seq": 42,
                  "uptime_ms": 10500,
                  "tank_a": {
                    "weight_g": null,
                    "level_pct": null,
                    "temp_c": null
                  },
                  "tank_b": {
                    "weight_g": null,
                    "level_pct": null,
                    "temp_c": null
                  },
                  "flow_lpm": null,
                  "actuators": {
                    "pump": false
                  },
                  "alarms": {
                    "overflow_a": false,
                    "overflow_b": false,
                    "sensor_fault": true
                  },
                  "mode": "auto"
                }
                """;

        TelemetryFrame frame = objectMapper.readValue(json, TelemetryFrame.class);

        assertNotNull(frame);
        assertEquals(1, frame.v());
        assertEquals(42L, frame.seq());
        assertEquals(10500L, frame.uptime_ms());
        assertNotNull(frame.tank_a());
        assertNull(frame.tank_a().level_pct());
        assertNull(frame.tank_a().weight_g());
        assertNull(frame.tank_a().temp_c());
        assertNotNull(frame.tank_b());
        assertNull(frame.tank_b().level_pct());
        assertNull(frame.tank_b().weight_g());
        assertNull(frame.tank_b().temp_c());
        assertNull(frame.flow_lpm());
        assertEquals(Boolean.FALSE, frame.actuators().get("pump"));
        assertEquals(Boolean.TRUE, frame.alarms().get("sensor_fault"));
        assertEquals("auto", frame.mode());
    }
}
