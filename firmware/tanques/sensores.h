#ifndef SENSORES_H
#define SENSORES_H

#include <Arduino.h>

/**
 * Estructura contenedora de lecturas de sensores del kit.
 * Banderas booleanas indican si la lectura física es válida o si debe emitirse null.
 */
struct LecturasSensores {
    bool tank_a_weight_valid;
    float tank_a_weight_g;
    bool tank_a_level_valid;
    float tank_a_level_pct;
    bool tank_a_temp_valid;
    float tank_a_temp_c;

    bool tank_b_weight_valid;
    float tank_b_weight_g;
    bool tank_b_level_valid;
    float tank_b_level_pct;
    bool tank_b_temp_valid;
    float tank_b_temp_c;

    bool flow_valid;
    float flow_lpm;

    bool overflow_a;
    bool overflow_b;
    bool sensor_fault;
};

/**
 * Inicializa los sensores o interrupciones necesarias.
 */
void sensores_init();

/**
 * Obtiene las lecturas actuales de los sensores y evalúa interlocks físicos.
 * @param out_lecturas Estructura receptora de datos.
 */
void sensores_read(LecturasSensores &out_lecturas);

#endif // SENSORES_H
