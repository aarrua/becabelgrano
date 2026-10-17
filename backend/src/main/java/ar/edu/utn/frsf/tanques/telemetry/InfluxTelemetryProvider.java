package ar.edu.utn.frsf.tanques.telemetry;

import ar.edu.utn.frsf.tanques.dto.TankTelemetry;
import ar.edu.utn.frsf.tanques.dto.TelemetryFrame;
import com.influxdb.client.InfluxDBClient;
import com.influxdb.client.InfluxDBClientFactory;
import com.influxdb.client.QueryApi;
import com.influxdb.query.FluxRecord;
import com.influxdb.query.FluxTable;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Component
@Profile("prod")
public class InfluxTelemetryProvider implements TelemetryProvider {

    private static final Logger log = LoggerFactory.getLogger(InfluxTelemetryProvider.class);

    private final InfluxDBClient influxDBClient;
    private final String bucket;
    private volatile Instant lastTelemetryTimestamp = null;

    @Autowired
    public InfluxTelemetryProvider(
            @Value("${tanques.influx.url:http://localhost:8086}") String url,
            @Value("${tanques.influx.token:tanques-super-secret-token-2025}") String token,
            @Value("${tanques.influx.org:utn-frsf}") String org,
            @Value("${tanques.influx.bucket:tanques}") String bucket
    ) {
        this.bucket = bucket;
        this.influxDBClient = InfluxDBClientFactory.create(url, token.toCharArray(), org, bucket);
    }

    @Override
    public boolean isTelemetryFresh() {
        Instant ts = lastTelemetryTimestamp;
        if (ts == null) {
            return false;
        }
        return Math.abs(java.time.Duration.between(ts, Instant.now()).toMillis()) <= 5000;
    }

    public Instant getLastTelemetryTimestamp() {
        return lastTelemetryTimestamp;
    }

    @Override
    public TelemetryFrame getLatestTelemetry() {
        String flux = String.format(
                "from(bucket: \"%s\") " +
                        "|> range(start: -5m) " +
                        "|> filter(fn: (r) => r[\"_measurement\"] == \"telemetry\") " +
                        "|> last()",
                bucket
        );

        Map<String, Object> fields = new HashMap<>();
        String mode = "auto";

        try {
            QueryApi queryApi = influxDBClient.getQueryApi();
            List<FluxTable> tables = queryApi.query(flux);

            Instant newestRecordTime = null;
            for (FluxTable table : tables) {
                for (FluxRecord record : table.getRecords()) {
                    String field = record.getField();
                    Object value = record.getValue();
                    if (field != null) {
                        fields.put(field, value);
                    }
                    if (record.getTime() != null) {
                        if (newestRecordTime == null || record.getTime().isAfter(newestRecordTime)) {
                            newestRecordTime = record.getTime();
                        }
                    }
                    if (record.getValueByKey("mode") != null) {
                        mode = record.getValueByKey("mode").toString();
                    }
                }
            }
            this.lastTelemetryTimestamp = newestRecordTime;
        } catch (Exception e) {
            log.error("Error consultando última telemetría en InfluxDB: {}", e.getMessage());
        }

        long seq = parseLong(fields.get("seq"), 0L);
        long uptimeMs = parseLong(fields.get("uptime_ms"), 0L);

        TankTelemetry tankA = new TankTelemetry(
                parseDouble(fields.get("tank_a_weight_g"), 0.0),
                parseDouble(fields.get("tank_a_level_pct"), 0.0),
                parseDouble(fields.get("tank_a_temp_c"), 0.0)
        );

        TankTelemetry tankB = new TankTelemetry(
                parseDouble(fields.get("tank_b_weight_g"), 0.0),
                parseDouble(fields.get("tank_b_level_pct"), 0.0),
                parseDouble(fields.get("tank_b_temp_c"), 0.0)
        );

        double flowLpm = parseDouble(fields.get("flow_lpm"), 0.0);

        Map<String, Boolean> actuators = new HashMap<>();
        if (isTelemetryFresh() && fields.containsKey("pump")) {
            actuators.put("pump", parseBoolean(fields.get("pump")));
        } else {
            actuators.put("pump", null);
        }

        Map<String, Boolean> alarms = new HashMap<>();
        alarms.put("overflow_a", parseBoolean(fields.get("overflow_a")));
        alarms.put("overflow_b", parseBoolean(fields.get("overflow_b")));
        alarms.put("sensor_fault", parseBoolean(fields.get("sensor_fault")));

        return new TelemetryFrame(1, seq, uptimeMs, tankA, tankB, flowLpm, actuators, alarms, mode);
    }

    private double parseDouble(Object val, double fallback) {
        if (val instanceof Number n) return n.doubleValue();
        if (val instanceof String s) {
            try { return Double.parseDouble(s); } catch (NumberFormatException ignored) {}
        }
        return fallback;
    }

    private long parseLong(Object val, long fallback) {
        if (val instanceof Number n) return n.longValue();
        if (val instanceof String s) {
            try { return Long.parseLong(s); } catch (NumberFormatException ignored) {}
        }
        return fallback;
    }

    private boolean parseBoolean(Object val) {
        if (val instanceof Boolean b) return b;
        if (val instanceof String s) return Boolean.parseBoolean(s);
        return false;
    }

    @PreDestroy
    public void cleanup() {
        if (influxDBClient != null) {
            influxDBClient.close();
        }
    }
}
