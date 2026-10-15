package ar.edu.utn.frsf.tanques;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class TanquesApplication {

    public static void main(String[] args) {
        SpringApplication.run(TanquesApplication.class, args);
    }
}
