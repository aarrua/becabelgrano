#include "actuadores.h"
#include "config.h"

static bool s_bomba_encendida = false;
static unsigned long s_bomba_inicio_ms = 0;
static bool s_pump_timeout_activa = false;

static inline uint8_t rele_pin_state(bool encendida) {
#if RELE_ACTIVO_ALTO
    return encendida ? HIGH : LOW;
#else
    return encendida ? LOW : HIGH;
#endif
}

void actuadores_init() {
    // 1. Configurar de inmediato el pin del relé como salida y forzar corte
    pinMode(PIN_RELE_BOMBA, OUTPUT);
    digitalWrite(PIN_RELE_BOMBA, rele_pin_state(false));

    // 2. Configurar el LED de diagnóstico integrado (pin 13)
    pinMode(PIN_LED_BUILTIN_ACTUADOR, OUTPUT);
    digitalWrite(PIN_LED_BUILTIN_ACTUADOR, LOW);

    s_bomba_encendida = false;
    s_bomba_inicio_ms = 0;
    s_pump_timeout_activa = false;
}

void actuadores_set_bomba(bool encendida) {
    if (encendida) {
        s_bomba_inicio_ms = millis();
        s_pump_timeout_activa = false;
    } else {
        s_pump_timeout_activa = false;
    }
    s_bomba_encendida = encendida;
    digitalWrite(PIN_RELE_BOMBA, rele_pin_state(encendida));
    digitalWrite(PIN_LED_BUILTIN_ACTUADOR, encendida ? HIGH : LOW);
}

bool actuadores_get_bomba() {
    return s_bomba_encendida;
}

void actuadores_verificar_watchdog() {
#if WATCHDOG_BOMBA_HABILITADO
    if (s_bomba_encendida) {
        if (millis() - s_bomba_inicio_ms >= PUMP_MAX_RUNTIME_MS) {
            // Corte preventivo por tiempo continuo máximo superado
            s_bomba_encendida = false;
            digitalWrite(PIN_RELE_BOMBA, rele_pin_state(false));
            digitalWrite(PIN_LED_BUILTIN_ACTUADOR, LOW);
            s_pump_timeout_activa = true;
        }
    }
#endif
}

bool actuadores_get_pump_timeout() {
    return s_pump_timeout_activa;
}

void actuadores_renovar_watchdog() {
    s_bomba_inicio_ms = millis();
    s_pump_timeout_activa = false;
}
