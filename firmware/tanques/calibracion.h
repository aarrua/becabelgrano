#ifndef CALIBRACION_H
#define CALIBRACION_H

#include <Arduino.h>

// Rangos aceptados por los comandos set_capacity y cal_flow.
// La capacidad se acota a la de la celda de carga (10 kg); el factor K cubre
// desde caudalímetros lentos (~100 pulsos/L) hasta YF-S401 (~5880 pulsos/L).
#define CAL_CAPACIDAD_MIN_G   100.0f
#define CAL_CAPACIDAD_MAX_G   10000.0f
#define CAL_FLOW_K_MIN        10.0f
#define CAL_FLOW_K_MAX        10000.0f
// Capacidad por defecto: por debajo de la del cilindro físico más chico (2450 g),
// para que un nivel calculado con el default nunca subestime el llenado real.
#define CAL_CAPACIDAD_DEFAULT_G 2000.0f

/**
 * Estructura de calibración de sensores físicos.
 * Se almacena en la memoria EEPROM interna del ATmega328P únicamente
 * mediante el comando explícito {"cmd":"save_cal"}.
 */
struct CalibracionData {
    uint16_t magic;         // 0x5441 ("TA" - Tanques)
    uint16_t version;       // Versión de esquema (1)
    long tare_a;            // Offset de tara celda A (cuentas raw HX711)
    float scale_a;          // Factor de escala celda A (cuentas / gramo)
    long tare_b;            // Offset de tara celda B
    float scale_b;          // Factor de escala celda B
    float max_weight_a;     // Capacidad máxima tanque A en gramos (default 2000.0 g)
    float max_weight_b;     // Capacidad máxima tanque B en gramos (default 2000.0 g)
    float flow_k_factor;    // Pulsos por litro del caudalímetro (ej. 450.0 para YF-S201)
    uint16_t checksum;      // Checksum de verificación de integridad
};

/**
 * Inicializa la calibración en memoria RAM leyendo desde la EEPROM.
 * Si la EEPROM está vacía (0xFF) o el checksum no coincide, se cargan
 * valores por defecto en RAM sin persistir nada automáticamente.
 */
void calibracion_init();

/**
 * Indica si la calibración vigente es confiable: true solo si se cargó de una
 * EEPROM válida (magic, versión y checksum) o si en esta sesión se fijaron tara,
 * escala y capacidad de AMBOS tanques. Tras reset_cal vuelve a false.
 * Mientras sea false, el encendido de la bomba se rechaza con "not_calibrated".
 */
bool calibracion_esta_calibrado();

/**
 * Retorna los parámetros de calibración vigentes en memoria RAM.
 */
const CalibracionData& calibracion_get();

/**
 * Establece el offset de tara de la celda de carga A en RAM.
 */
void calibracion_set_tare_a(long tare);

/**
 * Establece el offset de tara de la celda de carga B en RAM.
 */
void calibracion_set_tare_b(long tare);

/**
 * Establece el factor de escala (cuentas/g) de la celda A en RAM.
 */
void calibracion_set_scale_a(float scale);

/**
 * Establece el factor de escala (cuentas/g) de la celda B en RAM.
 */
void calibracion_set_scale_b(float scale);

/**
 * Establece la capacidad máxima (g) del tanque A en RAM.
 * @return false (sin modificar nada) si el valor es NaN o está fuera de
 *         [CAL_CAPACIDAD_MIN_G, CAL_CAPACIDAD_MAX_G].
 */
bool calibracion_set_capacity_a(float gramos);

/**
 * Establece la capacidad máxima (g) del tanque B en RAM.
 * @return false (sin modificar nada) si el valor es inválido (ver tanque A).
 */
bool calibracion_set_capacity_b(float gramos);

/**
 * Establece el factor K del caudalímetro (pulsos por litro) en RAM.
 * @return false (sin modificar nada) si el valor es NaN o está fuera de
 *         [CAL_FLOW_K_MIN, CAL_FLOW_K_MAX].
 */
bool calibracion_set_flow_k(float pulsos_por_litro);

/**
 * Restaura los parámetros de calibración a sus valores por defecto en RAM.
 * No modifica la EEPROM hasta que se reciba save_cal.
 */
void calibracion_reset_defaults();

/**
 * Persiste los parámetros vigentes en la memoria EEPROM con checksum.
 * ÚNICAMENTE se ejecuta ante el comando explícito {"cmd":"save_cal"}.
 * @return true si la escritura se completó con éxito.
 */
bool calibracion_save_eeprom();

#endif // CALIBRACION_H
