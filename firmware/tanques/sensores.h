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
 * Inicializa los sensores físicos (HX711, OneWire/DS18B20 y caudalímetro).
 */
void sensores_init();

/**
 * Obtiene las lecturas actuales de los sensores y evalúa interlocks físicos.
 * @param out_lecturas Estructura receptora de datos.
 */
void sensores_read(LecturasSensores &out_lecturas);

/**
 * Retorna las lecturas más recientes obtenidas en el último ciclo.
 */
const LecturasSensores& sensores_get_last();

/**
 * Lee las cuentas crudas del HX711 del Tanque A (para tara y calibración).
 * @return false (y no escribe out_raw) si el HX711 no está listo, si no hay
 *         sensores (MODO_SIM_SIN_SENSORES) o si el valor está saturado.
 */
bool sensores_leer_raw_a(long &out_raw);

/**
 * Ídem para el Tanque B.
 */
bool sensores_leer_raw_b(long &out_raw);

/**
 * Retorna true si el interlock de sobrellenado en Tanque A está activo.
 */
bool sensores_get_overflow_a();

/**
 * Retorna true si el interlock de sobrellenado en Tanque B está activo.
 */
bool sensores_get_overflow_b();

/**
 * Retorna true si hay falla en las celdas de carga (HX711) o en su plausibilidad.
 * La temperatura (DS18B20) no cuenta: su falla solo se informa con temp_c null.
 */
bool sensores_get_sensor_fault();

#endif // SENSORES_H
