package ar.edu.utn.frsf.tanques.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "tanques.geometry")
public class TankGeometryConfig {

    private TankGeometry tankA = new TankGeometry(100.0, 40.0, 4000.0);
    private TankGeometry tankB = new TankGeometry(70.0, 35.0, 2450.0);

    public TankGeometry getTankA() {
        return tankA;
    }

    public void setTankA(TankGeometry tankA) {
        this.tankA = tankA;
    }

    public TankGeometry getTankB() {
        return tankB;
    }

    public void setTankB(TankGeometry tankB) {
        this.tankB = tankB;
    }

    public static class TankGeometry {
        private double areaCm2;
        private double heightMaxCm;
        private double volumeMaxMl;

        public TankGeometry() {
        }

        public TankGeometry(double areaCm2, double heightMaxCm, double volumeMaxMl) {
            this.areaCm2 = areaCm2;
            this.heightMaxCm = heightMaxCm;
            this.volumeMaxMl = volumeMaxMl;
        }

        public double getAreaCm2() {
            return areaCm2;
        }

        public void setAreaCm2(double areaCm2) {
            this.areaCm2 = areaCm2;
        }

        public double getHeightMaxCm() {
            return heightMaxCm;
        }

        public void setHeightMaxCm(double heightMaxCm) {
            this.heightMaxCm = heightMaxCm;
        }

        public double getVolumeMaxMl() {
            return volumeMaxMl;
        }

        public void setVolumeMaxMl(double volumeMaxMl) {
            this.volumeMaxMl = volumeMaxMl;
        }
    }
}
