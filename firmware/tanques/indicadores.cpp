#include "indicadores.h"
#include "config.h"
#include <Adafruit_NeoPixel.h>

enum ClaseColor : uint8_t {
    COLOR_SIN_DATO = 0,
    COLOR_AZUL,
    COLOR_VERDE,
    COLOR_AMBAR,
    COLOR_ROJO
};

struct Tira {
    Adafruit_NeoPixel strip;
    uint32_t firma;   // Firma de la última imagen enviada a la tira
};

// Los buffers de pixeles (3 bytes por LED) los reserva la librería una sola vez
// al construir el objeto, por lo que no hay fragmentación del heap en ejecución.
static Tira s_tira_a = { Adafruit_NeoPixel(NEOPIXEL_LEDS_POR_TIRA, PIN_NEOPIXEL_A, NEO_GRB + NEO_KHZ800), 0xFFFFFFFFUL };
static Tira s_tira_b = { Adafruit_NeoPixel(NEOPIXEL_LEDS_POR_TIRA, PIN_NEOPIXEL_B, NEO_GRB + NEO_KHZ800), 0xFFFFFFFFUL };

static ClaseColor clase_por_temperatura(bool valida, float temp_c) {
    if (!valida) return COLOR_SIN_DATO;
    if (temp_c < NEOPIXEL_TEMP_AZUL_MAX_C) return COLOR_AZUL;
    if (temp_c < NEOPIXEL_TEMP_VERDE_MAX_C) return COLOR_VERDE;
    if (temp_c < NEOPIXEL_TEMP_AMBAR_MAX_C) return COLOR_AMBAR;
    return COLOR_ROJO;
}

static uint32_t rgb_de_clase(ClaseColor c) {
    switch (c) {
        case COLOR_AZUL:  return Adafruit_NeoPixel::Color(0, 0, 255);
        case COLOR_VERDE: return Adafruit_NeoPixel::Color(0, 255, 0);
        case COLOR_AMBAR: return Adafruit_NeoPixel::Color(255, 100, 0);
        case COLOR_ROJO:  return Adafruit_NeoPixel::Color(255, 0, 0);
        default:          return Adafruit_NeoPixel::Color(80, 80, 80); // sin dato de temperatura
    }
}

static uint8_t leds_encendidos(bool nivel_valido, float nivel_pct) {
    if (!nivel_valido || !(nivel_pct > 0.0f)) return 0;
    if (nivel_pct >= 100.0f) return NEOPIXEL_LEDS_POR_TIRA;
    return (uint8_t)((nivel_pct * NEOPIXEL_LEDS_POR_TIRA) / 100.0f + 0.5f);
}

/**
 * Refresca una tira si su imagen cambió. Devuelve true si llamó a show().
 */
static bool actualizar_tira(
    Tira &t, bool nivel_valido, float nivel_pct,
    bool temp_valida, float temp_c, bool alarma, bool parpadeo_on
) {
    uint8_t lit = leds_encendidos(nivel_valido, nivel_pct);
    ClaseColor clase = clase_por_temperatura(temp_valida, temp_c);
    // Con alarma, el último LED queda reservado para el parpadeo
    uint8_t tope = alarma ? (NEOPIXEL_LEDS_POR_TIRA - 1) : NEOPIXEL_LEDS_POR_TIRA;
    if (lit > tope) lit = tope;
    bool alarma_on = alarma && parpadeo_on;

    uint32_t firma = (uint32_t)lit | ((uint32_t)clase << 8) | ((uint32_t)alarma_on << 16) | ((uint32_t)alarma << 17);
    if (firma == t.firma) return false;
    t.firma = firma;

    uint32_t color = rgb_de_clase(clase);
    for (uint8_t i = 0; i < NEOPIXEL_LEDS_POR_TIRA; i++) {
        t.strip.setPixelColor(i, i < lit ? color : 0);
    }
    if (alarma) {
        t.strip.setPixelColor(NEOPIXEL_LEDS_POR_TIRA - 1, alarma_on ? Adafruit_NeoPixel::Color(255, 0, 0) : 0);
    }
    t.strip.show();
    return true;
}

void indicadores_init() {
    s_tira_a.strip.begin();
    s_tira_a.strip.setBrightness(NEOPIXEL_BRILLO);
    s_tira_a.strip.clear();
    s_tira_a.strip.show();

    s_tira_b.strip.begin();
    s_tira_b.strip.setBrightness(NEOPIXEL_BRILLO);
    s_tira_b.strip.clear();
    s_tira_b.strip.show();

    // Forzar el primer refresco con datos reales
    s_tira_a.firma = 0xFFFFFFFFUL;
    s_tira_b.firma = 0xFFFFFFFFUL;
}

void indicadores_actualizar(const LecturasSensores &l, bool pump_timeout) {
    // show() corta las interrupciones: no refrescar mientras entran bytes por serie
    if (Serial.available() > 0) return;

    bool parpadeo_on = ((millis() / NEOPIXEL_BLINK_MS) & 1UL) == 0;
    bool alarma_a = l.overflow_a || l.sensor_fault || pump_timeout;
    bool alarma_b = l.overflow_b || l.sensor_fault || pump_timeout;

    // A lo sumo una tira por llamada, para acotar el tiempo con interrupciones deshabilitadas
    if (actualizar_tira(s_tira_a, l.tank_a_level_valid, l.tank_a_level_pct,
                        l.tank_a_temp_valid, l.tank_a_temp_c, alarma_a, parpadeo_on)) {
        return;
    }
    actualizar_tira(s_tira_b, l.tank_b_level_valid, l.tank_b_level_pct,
                    l.tank_b_temp_valid, l.tank_b_temp_c, alarma_b, parpadeo_on);
}
