#include "sensores.h"
#include "config.h"

void sensores_init() {
#if MODO_SIM_SIN_SENSORES
    // En modo simulación sin sensores no se configuran periféricos físicos
#else
    // Reservado para sub-etapa 6.2 (HX711, DS18B20 y caudalímetro en D2)
#endif
}

void sensores_read(LecturasSensores &out) {
#if MODO_SIM_SIN_SENSORES
    // En modo sin sensores todas las lecturas físicas son nulas (null)
    // y la alarma sensor_fault se activa para advertir la ausencia de hardware
    out.tank_a_weight_valid = false;
    out.tank_a_weight_g = 0.0f;
    out.tank_a_level_valid = false;
    out.tank_a_level_pct = 0.0f;
    out.tank_a_temp_valid = false;
    out.tank_a_temp_c = 0.0f;

    out.tank_b_weight_valid = false;
    out.tank_b_weight_g = 0.0f;
    out.tank_b_level_valid = false;
    out.tank_b_level_pct = 0.0f;
    out.tank_b_temp_valid = false;
    out.tank_b_temp_c = 0.0f;

    out.flow_valid = false;
    out.flow_lpm = 0.0f;

    out.overflow_a = false;
    out.overflow_b = false;
    out.sensor_fault = true;
#else
    // Reservado para sub-etapa 6.2
#endif
}
