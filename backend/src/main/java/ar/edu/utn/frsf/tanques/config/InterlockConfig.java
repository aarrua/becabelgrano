package ar.edu.utn.frsf.tanques.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@ConfigurationProperties(prefix = "tanques.interlocks")
public class InterlockConfig {

    private double overflowThresholdPct = 85.0;

    public double getOverflowThresholdPct() {
        return overflowThresholdPct;
    }

    public void setOverflowThresholdPct(double overflowThresholdPct) {
        this.overflowThresholdPct = overflowThresholdPct;
    }
}
