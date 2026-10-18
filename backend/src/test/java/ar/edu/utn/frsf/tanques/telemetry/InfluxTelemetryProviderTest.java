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
}
