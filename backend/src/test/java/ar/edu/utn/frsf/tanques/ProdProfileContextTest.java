package ar.edu.utn.frsf.tanques;

import ar.edu.utn.frsf.tanques.gateway.ActuatorGateway;
import ar.edu.utn.frsf.tanques.gateway.BridgeActuatorGateway;
import ar.edu.utn.frsf.tanques.telemetry.InfluxTelemetryProvider;
import ar.edu.utn.frsf.tanques.telemetry.TelemetryProvider;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotNull;

@SpringBootTest(properties = {
        "JWT_SECRET=superSecretKeyForProdProfileTestAtLeast32Chars!",
        "DOCENTE_PASSWORD=docenteTestProdPass123",
        "ALUMNO_PASSWORD=alumnoTestProdPass123",
        "spring.datasource.url=jdbc:h2:mem:tanquestestprod;DB_CLOSE_DELAY=-1",
        "tanques.mqtt.port=19999" // Puerto no disponible para verificar arranque tolerante con broker caído
})
@ActiveProfiles("prod")
class ProdProfileContextTest {

    @Autowired
    private ActuatorGateway actuatorGateway;

    @Autowired
    private TelemetryProvider telemetryProvider;

    @Test
    void contextLoadsInProdProfileAndResolvesBridgeGateway() {
        assertNotNull(actuatorGateway, "El bean ActuatorGateway debe existir en contexto prod");
        assertInstanceOf(BridgeActuatorGateway.class, actuatorGateway,
                "El bean ActuatorGateway debe ser una instancia de BridgeActuatorGateway en perfil prod");

        assertNotNull(telemetryProvider, "El bean TelemetryProvider debe existir en contexto prod");
        assertInstanceOf(InfluxTelemetryProvider.class, telemetryProvider,
                "El bean TelemetryProvider debe ser una instancia de InfluxTelemetryProvider en perfil prod");
    }
}
