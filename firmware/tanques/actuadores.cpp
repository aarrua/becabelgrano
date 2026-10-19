#include "actuadores.h"
#include "config.h"

static bool s_bomba_encendida = false;

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
}

void actuadores_set_bomba(bool encendida) {
    s_bomba_encendida = encendida;
    digitalWrite(PIN_RELE_BOMBA, rele_pin_state(encendida));
    digitalWrite(PIN_LED_BUILTIN_ACTUADOR, encendida ? HIGH : LOW);
}

bool actuadores_get_bomba() {
    return s_bomba_encendida;
}
