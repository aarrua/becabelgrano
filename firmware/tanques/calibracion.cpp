#include "calibracion.h"
#include <EEPROM.h>

#define CAL_MAGIC   0x5441 // 'T' 'A'
#define CAL_VERSION 1

static CalibracionData s_cal;

// Origen de la confianza en la calibración (ver calibracion_esta_calibrado)
#define CAL_SESION_TARE_A  0x01
#define CAL_SESION_TARE_B  0x02
#define CAL_SESION_SCALE_A 0x04
#define CAL_SESION_SCALE_B 0x08
#define CAL_SESION_CAP_A   0x10
#define CAL_SESION_CAP_B   0x20
#define CAL_SESION_TODO    0x3F
static bool s_desde_eeprom = false;
static uint8_t s_sesion = 0;

static uint16_t calcular_checksum(const CalibracionData &data) {
    const uint8_t *p = (const uint8_t *)&data;
    size_t len = sizeof(CalibracionData) - sizeof(data.checksum);
    uint16_t sum = 0xAA55;
    for (size_t i = 0; i < len; i++) {
        sum = (sum << 1) ^ p[i];
    }
    return sum;
}

void calibracion_reset_defaults() {
    s_cal.magic = CAL_MAGIC;
    s_cal.version = CAL_VERSION;
    s_cal.tare_a = 0;
    s_cal.scale_a = 420.0f; // Cuentas por gramo típicas con celda de 10 kg
    s_cal.tare_b = 0;
    s_cal.scale_b = 420.0f;
    s_cal.max_weight_a = CAL_CAPACIDAD_DEFAULT_G; // Menor que el cilindro más chico: no subestima el llenado
    s_cal.max_weight_b = CAL_CAPACIDAD_DEFAULT_G;
    s_desde_eeprom = false;
    s_sesion = 0;
    s_cal.flow_k_factor = 450.0f; // Sensor YF-S201 nominal (~450 pulsos/L)
    s_cal.checksum = calcular_checksum(s_cal);
}

void calibracion_init() {
    CalibracionData temp;
    EEPROM.get(0, temp);

    if (temp.magic == CAL_MAGIC && temp.version == CAL_VERSION) {
        uint16_t cs = calcular_checksum(temp);
        if (cs == temp.checksum) {
            s_cal = temp;
            s_desde_eeprom = true;
            s_sesion = 0;
            return;
        }
    }

    // EEPROM vacía (0xFF) o checksum inválido: cargar valores por defecto en RAM
    // REGLA: Nada se persiste automáticamente en EEPROM sin comando explícito
    calibracion_reset_defaults();
}

bool calibracion_esta_calibrado() {
    return s_desde_eeprom || (s_sesion == CAL_SESION_TODO);
}

const CalibracionData& calibracion_get() {
    return s_cal;
}

void calibracion_set_tare_a(long tare) {
    s_cal.tare_a = tare;
    s_sesion |= CAL_SESION_TARE_A;
}

void calibracion_set_tare_b(long tare) {
    s_cal.tare_b = tare;
    s_sesion |= CAL_SESION_TARE_B;
}

void calibracion_set_scale_a(float scale) {
    if (scale > 0.0001f) {
        s_cal.scale_a = scale;
        s_sesion |= CAL_SESION_SCALE_A;
    }
}

void calibracion_set_scale_b(float scale) {
    if (scale > 0.0001f) {
        s_cal.scale_b = scale;
        s_sesion |= CAL_SESION_SCALE_B;
    }
}

// Las comparaciones afirmativas rechazan también NaN (toda comparación con NaN es falsa).
static bool en_rango(float v, float min_v, float max_v) {
    return (v >= min_v && v <= max_v);
}

bool calibracion_set_capacity_a(float gramos) {
    if (!en_rango(gramos, CAL_CAPACIDAD_MIN_G, CAL_CAPACIDAD_MAX_G)) return false;
    s_cal.max_weight_a = gramos;
    s_sesion |= CAL_SESION_CAP_A;
    return true;
}

bool calibracion_set_capacity_b(float gramos) {
    if (!en_rango(gramos, CAL_CAPACIDAD_MIN_G, CAL_CAPACIDAD_MAX_G)) return false;
    s_cal.max_weight_b = gramos;
    s_sesion |= CAL_SESION_CAP_B;
    return true;
}

bool calibracion_set_flow_k(float pulsos_por_litro) {
    if (!en_rango(pulsos_por_litro, CAL_FLOW_K_MIN, CAL_FLOW_K_MAX)) return false;
    s_cal.flow_k_factor = pulsos_por_litro;
    return true;
}

bool calibracion_save_eeprom() {
    s_cal.magic = CAL_MAGIC;
    s_cal.version = CAL_VERSION;
    s_cal.checksum = calcular_checksum(s_cal);
    EEPROM.put(0, s_cal);
    return true;
}
