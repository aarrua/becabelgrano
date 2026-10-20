#include "sensores.h"
#include "config.h"
#include "actuadores.h"
#include "calibracion.h"

#if !MODO_SIM_SIN_SENSORES
#include <OneWire.h>
#include <DallasTemperature.h>
#include <HX711.h>
#endif

static LecturasSensores s_last_lecturas = {
    false, 0.0f, false, 0.0f, false, 0.0f,
    false, 0.0f, false, 0.0f, false, 0.0f,
    false, 0.0f,
    false, false, true
};

static long s_raw_hx711_a = 0;
static long s_raw_hx711_b = 0;

#if !MODO_SIM_SIN_SENSORES
// Banderas de sobrellenado con histéresis. Arrancan activas (fail-safe) hasta la
// primera lectura válida bajo OVERFLOW_REARME_PCT.
static bool s_overflow_a = true;
static bool s_overflow_b = true;

/**
 * Histéresis del interlock: activa al llegar a OVERFLOW_THRESHOLD_PCT, se rearma
 * solo bajo OVERFLOW_REARME_PCT y con nivel inválido queda activa.
 */
static bool actualizar_overflow(bool activo, bool nivel_valido, float nivel_pct) {
    if (!nivel_valido) return true;
    if (nivel_pct >= OVERFLOW_THRESHOLD_PCT) return true;
    if (nivel_pct < OVERFLOW_REARME_PCT) return false;
    return activo;
}

static OneWire s_oneWire(PIN_DS18B20);
static DallasTemperature s_dallas(&s_oneWire);
static HX711 s_scale_a;
static HX711 s_scale_b;

static volatile unsigned long s_flow_pulse_count = 0;
static unsigned long s_last_flow_calc_ms = 0;

static void flow_sensor_isr() {
    s_flow_pulse_count++;
}

/**
 * Lee una celda HX711 y valida plausibilidad. Devuelve false (y deja peso y nivel
 * inválidos) si el HX711 no está listo, si el valor crudo está saturado
 * (cable cortado o celda fuera de rango) o si el peso es menor que
 * HX711_PESO_MIN_PLAUSIBLE_G. Los pesos negativos plausibles NO se recortan a 0
 * (una deriva de tara negativa debe verse); solo el nivel se acota a >= 0.
 */
static bool leer_celda(
    HX711 &hx, long tare, float scale, float max_w, long &raw_store,
    float &peso_g, bool &peso_valid, float &nivel_pct, bool &nivel_valid
) {
    peso_valid = false;
    nivel_valid = false;
    peso_g = 0.0f;
    nivel_pct = 0.0f;

    if (!hx.is_ready()) return false;

    long raw = hx.read();
    raw_store = raw;
    if (raw >= HX711_RAW_SATURADO || raw <= -HX711_RAW_SATURADO) return false;

    float w = (float)(raw - tare) / scale;
    if (w < HX711_PESO_MIN_PLAUSIBLE_G) return false;

    peso_g = w;
    peso_valid = true;
    float lvl = (w / max_w) * 100.0f;
    nivel_pct = (lvl < 0.0f) ? 0.0f : lvl;
    nivel_valid = true;
    return true;
}
#endif

void sensores_init() {
#if !MODO_SIM_SIN_SENSORES
    // 1. OneWire / DallasTemperature en modo asíncrono no bloqueante
    s_dallas.begin();
    s_dallas.setWaitForConversion(false);
    s_dallas.requestTemperatures(); // Primera conversión asíncrona

    // 2. Celdas de carga HX711
    s_scale_a.begin(PIN_HX711_A_DOUT, PIN_HX711_A_SCK);
    s_scale_b.begin(PIN_HX711_B_DOUT, PIN_HX711_B_SCK);

    // 3. Sensor de caudal por interrupción (INT0 en pin D2)
    pinMode(PIN_FLOW_SENSOR, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(PIN_FLOW_SENSOR), flow_sensor_isr, FALLING);
    s_last_flow_calc_ms = millis();
#endif
}

void sensores_read(LecturasSensores &out) {
#if MODO_SIM_SIN_SENSORES
    // En modo simulación sin sensores las lecturas físicas son null y sensor_fault es true
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
    const CalibracionData &cal = calibracion_get();
    bool fault = false;

    // =========================================================================
    // A. Sensores de Temperatura DS18B20 (lectura de conversión previa)
    // =========================================================================
    DeviceAddress addr_a = DS18B20_ADDR_A;
    DeviceAddress addr_b = DS18B20_ADDR_B;

    float tA = s_dallas.getTempC(addr_a);
    float tB = s_dallas.getTempC(addr_b);

    // Si las direcciones fijadas no responden, intentar por índice si hay dispositivos en el bus
    if ((tA == DEVICE_DISCONNECTED_C || tA < -55.0f || tA > 125.0f) && s_dallas.getDeviceCount() >= 1) {
        tA = s_dallas.getTempCByIndex(0);
        if (s_dallas.getDeviceCount() >= 2) {
            tB = s_dallas.getTempCByIndex(1);
        }
    }

    if (tA != DEVICE_DISCONNECTED_C && tA >= -55.0f && tA <= 125.0f) {
        out.tank_a_temp_valid = true;
        out.tank_a_temp_c = tA;
    } else {
        out.tank_a_temp_valid = false;
        out.tank_a_temp_c = 0.0f;
        fault = true;
    }

    if (tB != DEVICE_DISCONNECTED_C && tB >= -55.0f && tB <= 125.0f) {
        out.tank_b_temp_valid = true;
        out.tank_b_temp_c = tB;
    } else {
        out.tank_b_temp_valid = false;
        out.tank_b_temp_c = 0.0f;
        fault = true;
    }

    // Disparar próxima conversión no bloqueante para el ciclo siguiente
    s_dallas.requestTemperatures();

    // =========================================================================
    // B. Celdas de Carga HX711 (verificación de preparación sin bloqueo)
    // =========================================================================
    float max_a = (cal.max_weight_a > 1.0f) ? cal.max_weight_a : CAL_CAPACIDAD_DEFAULT_G;
    float max_b = (cal.max_weight_b > 1.0f) ? cal.max_weight_b : CAL_CAPACIDAD_DEFAULT_G;
    float scale_a = (cal.scale_a > 0.001f) ? cal.scale_a : 420.0f;
    float scale_b = (cal.scale_b > 0.001f) ? cal.scale_b : 420.0f;

    if (!leer_celda(s_scale_a, cal.tare_a, scale_a, max_a, s_raw_hx711_a,
                    out.tank_a_weight_g, out.tank_a_weight_valid,
                    out.tank_a_level_pct, out.tank_a_level_valid)) {
        fault = true;
    }
    if (!leer_celda(s_scale_b, cal.tare_b, scale_b, max_b, s_raw_hx711_b,
                    out.tank_b_weight_g, out.tank_b_weight_valid,
                    out.tank_b_level_pct, out.tank_b_level_valid)) {
        fault = true;
    }

    // =========================================================================
    // C. Sensor de Caudal
    // =========================================================================
    unsigned long now_ms = millis();
    unsigned long delta_ms = now_ms - s_last_flow_calc_ms;
    if (delta_ms > 0) {
        noInterrupts();
        unsigned long pulses = s_flow_pulse_count;
        s_flow_pulse_count = 0;
        interrupts();
        s_last_flow_calc_ms = now_ms;

        float k = (cal.flow_k_factor > 1.0f) ? cal.flow_k_factor : 450.0f;
        out.flow_lpm = ((float)pulses / k) * (60000.0f / (float)delta_ms);
        out.flow_valid = true;
    } else {
        out.flow_lpm = 0.0f;
        out.flow_valid = true;
    }

    // =========================================================================
    // D. Evaluación de Interlocks de Seguridad
    // =========================================================================
    s_overflow_a = actualizar_overflow(s_overflow_a, out.tank_a_level_valid, out.tank_a_level_pct);
    s_overflow_b = actualizar_overflow(s_overflow_b, out.tank_b_level_valid, out.tank_b_level_pct);
    out.overflow_a = s_overflow_a;
    out.overflow_b = s_overflow_b;
    out.sensor_fault = fault;

    // Corte preventivo por hardware si hay sobrellenado activo
    if (out.overflow_a || out.overflow_b) {
        if (actuadores_get_bomba()) {
            actuadores_set_bomba(false);
        }
    }

    // Fail-safe: sin nivel válido en algún tanque no se puede vigilar el sobrellenado,
    // así que la bomba no puede seguir encendida (cable cortado, HX711 caído, etc.).
    if (!out.tank_a_level_valid || !out.tank_b_level_valid) {
        out.sensor_fault = true;
        if (actuadores_get_bomba()) {
            actuadores_set_bomba(false);
        }
    }
#endif

    s_last_lecturas = out;
}

const LecturasSensores& sensores_get_last() {
    return s_last_lecturas;
}

#if !MODO_SIM_SIN_SENSORES
static bool leer_raw(HX711 &hx, long &store, long &out_raw) {
    if (!hx.is_ready()) return false;
    long raw = hx.read();
    if (raw >= HX711_RAW_SATURADO || raw <= -HX711_RAW_SATURADO) return false;
    store = raw;
    out_raw = raw;
    return true;
}
#endif

bool sensores_leer_raw_a(long &out_raw) {
#if !MODO_SIM_SIN_SENSORES
    return leer_raw(s_scale_a, s_raw_hx711_a, out_raw);
#else
    (void)out_raw;
    return false;
#endif
}

bool sensores_leer_raw_b(long &out_raw) {
#if !MODO_SIM_SIN_SENSORES
    return leer_raw(s_scale_b, s_raw_hx711_b, out_raw);
#else
    (void)out_raw;
    return false;
#endif
}

bool sensores_get_overflow_a() {
    return s_last_lecturas.overflow_a;
}

bool sensores_get_overflow_b() {
    return s_last_lecturas.overflow_b;
}

bool sensores_get_sensor_fault() {
    return s_last_lecturas.sensor_fault;
}
