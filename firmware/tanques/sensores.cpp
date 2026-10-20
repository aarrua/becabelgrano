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
static OneWire s_oneWire(PIN_DS18B20);
static DallasTemperature s_dallas(&s_oneWire);
static HX711 s_scale_a;
static HX711 s_scale_b;

static volatile unsigned long s_flow_pulse_count = 0;
static unsigned long s_last_flow_calc_ms = 0;

static void flow_sensor_isr() {
    s_flow_pulse_count++;
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
    // Tanque A
    if (s_scale_a.is_ready()) {
        long raw_a = s_scale_a.read();
        s_raw_hx711_a = raw_a;
        float scale = (cal.scale_a > 0.001f) ? cal.scale_a : 420.0f;
        float wA = (float)(raw_a - cal.tare_a) / scale;
        if (wA < 0.0f) wA = 0.0f;
        out.tank_a_weight_g = wA;
        out.tank_a_weight_valid = true;

        float max_w = (cal.max_weight_a > 1.0f) ? cal.max_weight_a : 4000.0f;
        float lvlA = (wA / max_w) * 100.0f;
        if (lvlA < 0.0f) lvlA = 0.0f;
        out.tank_a_level_pct = lvlA;
        out.tank_a_level_valid = true;
    } else {
        out.tank_a_weight_valid = false;
        out.tank_a_level_valid = false;
        fault = true;
    }

    // Tanque B
    if (s_scale_b.is_ready()) {
        long raw_b = s_scale_b.read();
        s_raw_hx711_b = raw_b;
        float scale = (cal.scale_b > 0.001f) ? cal.scale_b : 420.0f;
        float wB = (float)(raw_b - cal.tare_b) / scale;
        if (wB < 0.0f) wB = 0.0f;
        out.tank_b_weight_g = wB;
        out.tank_b_weight_valid = true;

        float max_w = (cal.max_weight_b > 1.0f) ? cal.max_weight_b : 2450.0f;
        float lvlB = (wB / max_w) * 100.0f;
        if (lvlB < 0.0f) lvlB = 0.0f;
        out.tank_b_level_pct = lvlB;
        out.tank_b_level_valid = true;
    } else {
        out.tank_b_weight_valid = false;
        out.tank_b_level_valid = false;
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
    out.overflow_a = (out.tank_a_level_valid && out.tank_a_level_pct >= OVERFLOW_THRESHOLD_PCT);
    out.overflow_b = (out.tank_b_level_valid && out.tank_b_level_pct >= OVERFLOW_THRESHOLD_PCT);
    out.sensor_fault = fault;

    // Corte preventivo por hardware si hay sobrellenado activo
    if (out.overflow_a || out.overflow_b) {
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

long sensores_get_raw_hx711_a() {
#if !MODO_SIM_SIN_SENSORES
    if (s_scale_a.is_ready()) {
        s_raw_hx711_a = s_scale_a.read();
    }
#endif
    return s_raw_hx711_a;
}

long sensores_get_raw_hx711_b() {
#if !MODO_SIM_SIN_SENSORES
    if (s_scale_b.is_ready()) {
        s_raw_hx711_b = s_scale_b.read();
    }
#endif
    return s_raw_hx711_b;
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
