package ar.edu.utn.frsf.tanques.telemetry;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
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

    @Test
    @DisplayName("Influx inaccesible retorna telemetría degradada, pump=null, sensor_fault=true y mode=offline sin lanzar 500")
    void testWhenInfluxInaccessible_ReturnsDegradedTelemetry() {
        com.influxdb.client.InfluxDBClient mockClient = org.mockito.Mockito.mock(com.influxdb.client.InfluxDBClient.class);
        com.influxdb.client.QueryApi mockQueryApi = org.mockito.Mockito.mock(com.influxdb.client.QueryApi.class);
        org.mockito.Mockito.when(mockClient.getQueryApi()).thenReturn(mockQueryApi);
        org.mockito.Mockito.when(mockQueryApi.query(org.mockito.ArgumentMatchers.anyString()))
                .thenThrow(new com.influxdb.exceptions.InfluxException("Connection refused to InfluxDB:8086"));

        InfluxTelemetryProvider provider = new InfluxTelemetryProvider(mockClient, "tanques");

        ar.edu.utn.frsf.tanques.dto.TelemetryFrame frame = provider.getLatestTelemetry();

        assertNotNull(frame, "La trama no debe ser null ante fallo de conexión");
        assertEquals("offline", frame.mode(), "El modo debe ser offline cuando Influx está inaccesible");
        assertTrue(frame.alarms().get("sensor_fault"), "sensor_fault debe ser true como indicador de falla de telemetría");
        assertNull(frame.actuators().get("pump"), "pump debe ser null (desconocido)");
        assertFalse(provider.isTelemetryFresh(), "isTelemetryFresh() debe ser false cuando Influx está caído");
    }

    @Test
    @DisplayName("Token de Influx inválido retorna telemetría degradada, pump=null, sensor_fault=true y mode=offline")
    void testWhenInfluxTokenInvalid_ReturnsDegradedTelemetry() {
        com.influxdb.client.InfluxDBClient mockClient = org.mockito.Mockito.mock(com.influxdb.client.InfluxDBClient.class);
        com.influxdb.client.QueryApi mockQueryApi = org.mockito.Mockito.mock(com.influxdb.client.QueryApi.class);
        org.mockito.Mockito.when(mockClient.getQueryApi()).thenReturn(mockQueryApi);
        com.influxdb.exceptions.UnauthorizedException mockUnauthorized =
                org.mockito.Mockito.mock(com.influxdb.exceptions.UnauthorizedException.class);
        org.mockito.Mockito.when(mockQueryApi.query(org.mockito.ArgumentMatchers.anyString()))
                .thenThrow(mockUnauthorized);

        InfluxTelemetryProvider provider = new InfluxTelemetryProvider(mockClient, "tanques");

        ar.edu.utn.frsf.tanques.dto.TelemetryFrame frame = provider.getLatestTelemetry();

        assertNotNull(frame, "La trama no debe ser null ante token inválido");
        assertEquals("offline", frame.mode(), "El modo debe ser offline ante error 401 de Influx");
        assertTrue(frame.alarms().get("sensor_fault"), "sensor_fault debe ser true");
        assertNull(frame.actuators().get("pump"), "pump debe ser null");
        assertFalse(provider.isTelemetryFresh(), "isTelemetryFresh() debe ser false");
    }

    @Test
    @DisplayName("Resultado vacío de Influx retorna telemetría degradada con pump=null y sensor_fault=true")
    void testWhenInfluxResultEmpty_ReturnsDegradedTelemetry() {
        com.influxdb.client.InfluxDBClient mockClient = org.mockito.Mockito.mock(com.influxdb.client.InfluxDBClient.class);
        com.influxdb.client.QueryApi mockQueryApi = org.mockito.Mockito.mock(com.influxdb.client.QueryApi.class);
        org.mockito.Mockito.when(mockClient.getQueryApi()).thenReturn(mockQueryApi);
        org.mockito.Mockito.when(mockQueryApi.query(org.mockito.ArgumentMatchers.anyString()))
                .thenReturn(java.util.Collections.emptyList());

        InfluxTelemetryProvider provider = new InfluxTelemetryProvider(mockClient, "tanques");

        ar.edu.utn.frsf.tanques.dto.TelemetryFrame frame = provider.getLatestTelemetry();

        assertNotNull(frame, "La trama no debe ser null cuando no hay registros");
        assertEquals("offline", frame.mode(), "El modo debe ser offline cuando no hay datos");
        assertTrue(frame.alarms().get("sensor_fault"), "sensor_fault debe ser true");
        assertNull(frame.actuators().get("pump"), "pump debe ser null");
        assertFalse(provider.isTelemetryFresh(), "isTelemetryFresh() debe ser false");
    }

    @Test
    @DisplayName("Trama con sensores en null (MODO_SIM_SIN_SENSORES) retorna niveles y temperaturas en null")
    void testWhenSensorsAreNull_ReturnsTelemetryWithNullLevelsAndTemp() {
        com.influxdb.client.InfluxDBClient mockClient = org.mockito.Mockito.mock(com.influxdb.client.InfluxDBClient.class);
        com.influxdb.client.QueryApi mockQueryApi = org.mockito.Mockito.mock(com.influxdb.client.QueryApi.class);
        org.mockito.Mockito.when(mockClient.getQueryApi()).thenReturn(mockQueryApi);

        com.influxdb.query.FluxTable table = new com.influxdb.query.FluxTable();
        java.time.Instant now = java.time.Instant.now();

        java.util.List<com.influxdb.query.FluxRecord> records = new java.util.ArrayList<>();
        records.add(createMockRecord("seq", 101L, now, "auto"));
        records.add(createMockRecord("uptime_ms", 5000L, now, "auto"));
        records.add(createMockRecord("pump", false, now, "auto"));
        records.add(createMockRecord("overflow_a", false, now, "auto"));
        records.add(createMockRecord("overflow_b", false, now, "auto"));
        records.add(createMockRecord("sensor_fault", true, now, "auto"));
        table.getRecords().addAll(records);

        org.mockito.Mockito.when(mockQueryApi.query(org.mockito.ArgumentMatchers.anyString()))
                .thenReturn(java.util.List.of(table));

        InfluxTelemetryProvider provider = new InfluxTelemetryProvider(mockClient, "tanques");
        ar.edu.utn.frsf.tanques.dto.TelemetryFrame frame = provider.getLatestTelemetry();

        assertNotNull(frame, "La trama no debe ser null");
        assertEquals(101L, frame.seq());
        assertEquals(5000L, frame.uptime_ms());
        assertEquals("auto", frame.mode());
        assertNull(frame.tank_a().level_pct(), "tank_a.level_pct debe ser null si el sensor está ausente");
        assertNull(frame.tank_a().temp_c(), "tank_a.temp_c debe ser null si el sensor está ausente");
        assertNull(frame.tank_a().weight_g(), "tank_a.weight_g debe ser null si el sensor está ausente");
        assertNull(frame.tank_b().level_pct(), "tank_b.level_pct debe ser null si el sensor está ausente");
        assertNull(frame.tank_b().temp_c(), "tank_b.temp_c debe ser null si el sensor está ausente");
        assertNull(frame.tank_b().weight_g(), "tank_b.weight_g debe ser null si el sensor está ausente");
        assertNull(frame.flow_lpm(), "flow_lpm debe ser null si el sensor está ausente");
        assertEquals(Boolean.FALSE, frame.actuators().get("pump"));
        assertEquals(Boolean.TRUE, frame.alarms().get("sensor_fault"));
        assertTrue(provider.isTelemetryFresh(), "isTelemetryFresh() debe ser true al haber registros recientes");
    }

    private com.influxdb.query.FluxRecord createMockRecord(String field, Object value, java.time.Instant time, String mode) {
        com.influxdb.query.FluxRecord r = org.mockito.Mockito.mock(com.influxdb.query.FluxRecord.class);
        org.mockito.Mockito.when(r.getField()).thenReturn(field);
        org.mockito.Mockito.when(r.getValue()).thenReturn(value);
        org.mockito.Mockito.when(r.getTime()).thenReturn(time);
        org.mockito.Mockito.when(r.getValueByKey("mode")).thenReturn(mode);
        return r;
    }
}
