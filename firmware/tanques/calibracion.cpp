#include "calibracion.h"
#include <EEPROM.h>

#define CAL_MAGIC   0x5441 // 'T' 'A'
#define CAL_VERSION 1

static CalibracionData s_cal;

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
    s_cal.max_weight_a = 4000.0f; // 4000 ml de capacidad máxima en A (~4000 g agua)
    s_cal.max_weight_b = 2450.0f; // 2450 ml de capacidad máxima en B (~2450 g agua)
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
            return;
        }
    }

    // EEPROM vacía (0xFF) o checksum inválido: cargar valores por defecto en RAM
    // REGLA: Nada se persiste automáticamente en EEPROM sin comando explícito
    calibracion_reset_defaults();
}

const CalibracionData& calibracion_get() {
    return s_cal;
}

void calibracion_set_tare_a(long tare) {
    s_cal.tare_a = tare;
}

void calibracion_set_tare_b(long tare) {
    s_cal.tare_b = tare;
}

void calibracion_set_scale_a(float scale) {
    if (scale > 0.0001f) {
        s_cal.scale_a = scale;
    }
}

void calibracion_set_scale_b(float scale) {
    if (scale > 0.0001f) {
        s_cal.scale_b = scale;
    }
}

// Las comparaciones afirmativas rechazan también NaN (toda comparación con NaN es falsa).
static bool en_rango(float v, float min_v, float max_v) {
    return (v >= min_v && v <= max_v);
}

bool calibracion_set_capacity_a(float gramos) {
    if (!en_rango(gramos, CAL_CAPACIDAD_MIN_G, CAL_CAPACIDAD_MAX_G)) return false;
    s_cal.max_weight_a = gramos;
    return true;
}

bool calibracion_set_capacity_b(float gramos) {
    if (!en_rango(gramos, CAL_CAPACIDAD_MIN_G, CAL_CAPACIDAD_MAX_G)) return false;
    s_cal.max_weight_b = gramos;
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
