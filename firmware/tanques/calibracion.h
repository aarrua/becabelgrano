#ifndef CALIBRACION_H
#define CALIBRACION_H

#include <Arduino.h>

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
    float max_weight_a;     // Capacidad máxima tanque A en gramos (4000.0 g)
    float max_weight_b;     // Capacidad máxima tanque B en gramos (2450.0 g)
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
