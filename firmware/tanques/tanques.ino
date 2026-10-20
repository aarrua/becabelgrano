/**
 * ==============================================================================
 * Kit Didáctico de Tanques Interconectados - UTN FRSF / GITDA
 * Firmware Arduino Uno (ATmega328P)
 * ==============================================================================
 * Arquitectura modular de telemetría y control sin asignación dinámica de memoria (heap).
 * 
 * Sub-Etapa 6.2:
 * - Sensores reales (HX711, OneWire/DS18B20 asíncrono, caudalímetro por interrupciones).
 * - Interlocks de sobrellenado (>= 85%) y rechazo de activación ante sensor_fault.
 * - Watchdog de seguridad de bomba (máximo 60 s de bombeo continuo).
 * - Calibración en EEPROM con comando explícito {"cmd":"save_cal"} y checksum.
 * ==============================================================================
 */

#include "config.h"
#include "actuadores.h"
#include "sensores.h"
#include "calibracion.h"
#include "protocolo.h"

static unsigned long s_last_telemetry_ms = 0;
static unsigned long s_seq_counter = 0;

void setup() {
    // 1. REGLA ESTRICTA DE SEGURIDAD FÍSICA:
    // Asegurar actuadores y relé en estado APAGADO antes de cualquier otra lógica.
    actuadores_init();

    // 2. Inicializar parámetros de calibración desde EEPROM (o defaults si vacía/corrupta)
    calibracion_init();

    // 3. Inicializar comunicación serial (115200 bps, 8N1)
    protocolo_init();

    // 4. Inicializar subsistema de sensores
    sensores_init();

    s_last_telemetry_ms = millis();
}

void loop() {
    // 1. Atender comandos entrantes por puerto serie de forma continua y no bloqueante
    protocolo_procesar_serie();

    // 2. Verificar watchdog de tiempo continuo máximo de encendido de bomba
    actuadores_verificar_watchdog();

    // 2. Emisión periódica de telemetría a frecuencia de 1 Hz (1000 ms)
    unsigned long now_ms = millis();
    if (now_ms - s_last_telemetry_ms >= TELEMETRY_INTERVAL_MS) {
        s_last_telemetry_ms = now_ms;
        s_seq_counter++;

        LecturasSensores lecturas;
        sensores_read(lecturas);

        protocolo_emitir_telemetria(
            s_seq_counter,
            now_ms,
            lecturas,
            actuadores_get_bomba()
        );
    }
}
