#include "protocolo.h"
#include "config.h"
#include "actuadores.h"
#include "sensores.h"
#include "calibracion.h"
#include <string.h>
#include <stdlib.h>

static char s_rx_buffer[PROTOCOL_RX_BUFFER_SIZE];
static uint8_t s_rx_index = 0;
static bool s_rx_overflow = false;

void protocolo_init() {
    Serial.begin(SERIAL_BAUDRATE);
    s_rx_index = 0;
    s_rx_overflow = false;
}

void protocolo_emitir_telemetria(
    unsigned long seq,
    unsigned long uptime_ms,
    const LecturasSensores &s,
    bool bomba_estado
) {
    char numBuf[16];

    Serial.print(F("{\"v\":1,\"seq\":"));
    Serial.print(seq);
    Serial.print(F(",\"uptime_ms\":"));
    Serial.print(uptime_ms);

    // =========================================================================
    // tank_a
    // =========================================================================
    Serial.print(F(",\"tank_a\":{\"weight_g\":"));
    if (s.tank_a_weight_valid) {
        dtostrf(s.tank_a_weight_g, 1, 1, numBuf);
        Serial.print(numBuf);
    } else {
        Serial.print(F("null"));
    }
    Serial.print(F(",\"level_pct\":"));
    if (s.tank_a_level_valid) {
        dtostrf(s.tank_a_level_pct, 1, 1, numBuf);
        Serial.print(numBuf);
    } else {
        Serial.print(F("null"));
    }
    Serial.print(F(",\"temp_c\":"));
    if (s.tank_a_temp_valid) {
        dtostrf(s.tank_a_temp_c, 1, 1, numBuf);
        Serial.print(numBuf);
    } else {
        Serial.print(F("null"));
    }
    Serial.print(F("}"));

    // =========================================================================
    // tank_b
    // =========================================================================
    Serial.print(F(",\"tank_b\":{\"weight_g\":"));
    if (s.tank_b_weight_valid) {
        dtostrf(s.tank_b_weight_g, 1, 1, numBuf);
        Serial.print(numBuf);
    } else {
        Serial.print(F("null"));
    }
    Serial.print(F(",\"level_pct\":"));
    if (s.tank_b_level_valid) {
        dtostrf(s.tank_b_level_pct, 1, 1, numBuf);
        Serial.print(numBuf);
    } else {
        Serial.print(F("null"));
    }
    Serial.print(F(",\"temp_c\":"));
    if (s.tank_b_temp_valid) {
        dtostrf(s.tank_b_temp_c, 1, 1, numBuf);
        Serial.print(numBuf);
    } else {
        Serial.print(F("null"));
    }
    Serial.print(F("}"));

    // =========================================================================
    // flow_lpm
    // =========================================================================
    Serial.print(F(",\"flow_lpm\":"));
    if (s.flow_valid) {
        dtostrf(s.flow_lpm, 1, 2, numBuf);
        Serial.print(numBuf);
    } else {
        Serial.print(F("null"));
    }

    // =========================================================================
    // actuators
    // =========================================================================
    Serial.print(F(",\"actuators\":{\"pump\":"));
    Serial.print(bomba_estado ? F("true") : F("false"));
    Serial.print(F("}"));

    // =========================================================================
    // alarms
    // =========================================================================
    Serial.print(F(",\"alarms\":{\"overflow_a\":"));
    Serial.print(s.overflow_a ? F("true") : F("false"));
    Serial.print(F(",\"overflow_b\":"));
    Serial.print(s.overflow_b ? F("true") : F("false"));
    Serial.print(F(",\"sensor_fault\":"));
    Serial.print(s.sensor_fault ? F("true") : F("false"));
    Serial.print(F(",\"pump_timeout\":"));
    Serial.print(actuadores_get_pump_timeout() ? F("true") : F("false"));
    Serial.print(F("}"));

    // =========================================================================
    // mode
    // =========================================================================
    Serial.print(F(",\"mode\":\"auto\"}\n"));
}

static void responder_ack(const char *ack_id, bool ok, const char *reason) {
    Serial.print(F("{\"ack\":\""));
    Serial.print(ack_id);
    Serial.print(F("\",\"ok\":"));
    Serial.print(ok ? F("true") : F("false"));
    if (!ok && reason != nullptr) {
        Serial.print(F(",\"reason\":\""));
        Serial.print(reason);
        Serial.print(F("\""));
    }
    Serial.print(F("}\n"));
}

/**
 * Parser liviano de strings JSON sin asignación dinámica de memoria.
 * Busca `"key"` y copia el contenido entre comillas subsiguiente en out.
 */
static bool extract_json_string(const char *json, const char *key, char *out, size_t max_len) {
    if (!json || !key || !out || max_len == 0) return false;

    // Buscar "key"
    char key_pattern[24];
    size_t key_len = strlen(key);
    if (key_len + 3 >= sizeof(key_pattern)) return false;
    key_pattern[0] = '\"';
    memcpy(key_pattern + 1, key, key_len);
    key_pattern[key_len + 1] = '\"';
    key_pattern[key_len + 2] = '\0';

    const char *p = strstr(json, key_pattern);
    if (!p) return false;
    p += key_len + 2;

    // Buscar ':'
    while (*p && *p != ':') {
        p++;
    }
    if (*p != ':') return false;
    p++;

    // Buscar comilla de apertura
    while (*p && *p != '\"') {
        p++;
    }
    if (*p != '\"') return false;
    p++; // Avanzar tras la comilla de apertura

    // Copiar hasta comilla de cierre
    size_t copied = 0;
    while (*p && *p != '\"' && copied < max_len - 1) {
        out[copied++] = *p++;
    }
    out[copied] = '\0';

    return (*p == '\"');
}

/**
 * Parser liviano de valores booleanos JSON.
 * Busca `"key"` y detecta si su valor es true o false.
 */
static bool extract_json_bool(const char *json, const char *key, bool &out_val) {
    if (!json || !key) return false;

    char key_pattern[24];
    size_t key_len = strlen(key);
    if (key_len + 3 >= sizeof(key_pattern)) return false;
    key_pattern[0] = '\"';
    memcpy(key_pattern + 1, key, key_len);
    key_pattern[key_len + 1] = '\"';
    key_pattern[key_len + 2] = '\0';

    const char *p = strstr(json, key_pattern);
    if (!p) return false;
    p += key_len + 2;

    while (*p && *p != ':') {
        p++;
    }
    if (*p != ':') return false;
    p++;

    while (*p && (*p == ' ' || *p == '\t')) {
        p++;
    }

    if (strncmp(p, "true", 4) == 0) {
        out_val = true;
        return true;
    } else if (strncmp(p, "false", 5) == 0) {
        out_val = false;
        return true;
    }

    return false;
}

/**
 * Parser liviano de números de punto flotante JSON.
 * Busca `"key"` y parsea el float subsiguiente.
 */
static bool extract_json_float(const char *json, const char *key, float &out_val) {
    if (!json || !key) return false;

    char key_pattern[24];
    size_t key_len = strlen(key);
    if (key_len + 3 >= sizeof(key_pattern)) return false;
    key_pattern[0] = '\"';
    memcpy(key_pattern + 1, key, key_len);
    key_pattern[key_len + 1] = '\"';
    key_pattern[key_len + 2] = '\0';

    const char *p = strstr(json, key_pattern);
    if (!p) return false;
    p += key_len + 2;

    while (*p && *p != ':') {
        p++;
    }
    if (*p != ':') return false;
    p++;

    while (*p && (*p == ' ' || *p == '\t')) {
        p++;
    }

    if (*p == '\0' || (*p != '-' && *p != '+' && (*p < '0' || *p > '9'))) {
        return false;
    }

    out_val = (float)atof(p);
    return true;
}

static void procesar_comando_linea(const char *line) {
    char cmd_id[20];
    char cmd_name[16];

    bool has_id = extract_json_string(line, "id", cmd_id, sizeof(cmd_id));
    const char *ack_id = has_id ? cmd_id : "cal";

    // Extraer cmd obligatorio
    if (!extract_json_string(line, "cmd", cmd_name, sizeof(cmd_name))) {
        responder_ack(has_id ? cmd_id : "?", false, "unknown_cmd");
        return;
    }

    // =========================================================================
    // Comando: {"cmd":"save_cal"}
    // Persiste parámetros de calibración vigentes en EEPROM con checksum.
    // =========================================================================
    if (strcmp(cmd_name, "save_cal") == 0) {
        // No persistir valores de fábrica: al reiniciar pasarían por "calibrados"
        if (!calibracion_esta_calibrado()) {
            responder_ack(ack_id, false, "not_calibrated");
            return;
        }
        calibracion_save_eeprom();
        responder_ack(ack_id, true, nullptr);
        return;
    }

    // =========================================================================
    // Comando: {"cmd":"reset_cal"}
    // Restaura parámetros por defecto en RAM sin persistir en EEPROM.
    // =========================================================================
    if (strcmp(cmd_name, "reset_cal") == 0) {
        calibracion_reset_defaults();
        responder_ack(ack_id, true, nullptr);
        return;
    }

    // =========================================================================
    // Comando: {"cmd":"tare","tank":"a"|"b"}
    // Fija offset de tara para la celda correspondiente en RAM.
    // =========================================================================
    if (strcmp(cmd_name, "tare") == 0) {
        char tank[8];
        if (extract_json_string(line, "tank", tank, sizeof(tank))) {
            bool es_a = (strcmp(tank, "a") == 0);
            if (es_a || strcmp(tank, "b") == 0) {
                long raw = 0;
                // Con el HX711 no listo o saturado no se toca la tara vigente
                bool leido = es_a ? sensores_leer_raw_a(raw) : sensores_leer_raw_b(raw);
                if (!leido) {
                    responder_ack(ack_id, false, "sensor_not_ready");
                    return;
                }
                if (es_a) {
                    calibracion_set_tare_a(raw);
                } else {
                    calibracion_set_tare_b(raw);
                }
                responder_ack(ack_id, true, nullptr);
                return;
            }
        }
        responder_ack(ack_id, false, "invalid_tank");
        return;
    }

    // =========================================================================
    // Comando: {"cmd":"cal_scale","tank":"a"|"b","scale":420.5}
    // Fija factor de escala (cuentas/g) para la celda de carga en RAM.
    // =========================================================================
    if (strcmp(cmd_name, "cal_scale") == 0) {
        char tank[8];
        float scale = 0.0f;
        if (extract_json_string(line, "tank", tank, sizeof(tank)) &&
            extract_json_float(line, "scale", scale)) {
            bool ok = false;
            if (strcmp(tank, "a") == 0) {
                ok = calibracion_set_scale_a(scale);
            } else if (strcmp(tank, "b") == 0) {
                ok = calibracion_set_scale_b(scale);
            }
            if (ok) {
                responder_ack(ack_id, true, nullptr);
                return;
            }
        }
        responder_ack(ack_id, false, "invalid_scale");
        return;
    }

    // =========================================================================
    // Comando: {"cmd":"set_capacity","tank":"a"|"b","grams":4000}
    // Fija la capacidad máxima del tanque (100..10000 g) en RAM.
    // =========================================================================
    if (strcmp(cmd_name, "set_capacity") == 0) {
        char tank[8];
        float grams = 0.0f;
        if (extract_json_string(line, "tank", tank, sizeof(tank)) &&
            extract_json_float(line, "grams", grams)) {
            bool ok = false;
            if (strcmp(tank, "a") == 0) {
                ok = calibracion_set_capacity_a(grams);
            } else if (strcmp(tank, "b") == 0) {
                ok = calibracion_set_capacity_b(grams);
            }
            if (ok) {
                responder_ack(ack_id, true, nullptr);
                return;
            }
        }
        responder_ack(ack_id, false, "invalid_capacity");
        return;
    }

    // =========================================================================
    // Comando: {"cmd":"cal_flow","pulses_per_l":450}
    // Fija el factor K del caudalímetro (10..10000 pulsos/L) en RAM.
    // =========================================================================
    if (strcmp(cmd_name, "cal_flow") == 0) {
        float k = 0.0f;
        if (extract_json_float(line, "pulses_per_l", k) && calibracion_set_flow_k(k)) {
            responder_ack(ack_id, true, nullptr);
            return;
        }
        responder_ack(ack_id, false, "invalid_flow_k");
        return;
    }

    // =========================================================================
    // Comando: {"id":"c1","cmd":"set","target":"pump","value":true|false}
    // Control de actuadores físicos con interlocks y watchdog.
    // =========================================================================
    if (strcmp(cmd_name, "set") == 0) {
        if (!has_id) {
            responder_ack("?", false, "missing_id");
            return;
        }

        char target[16];
        bool value_bool = false;

        // Extraer target ("pump")
        if (!extract_json_string(line, "target", target, sizeof(target)) || strcmp(target, "pump") != 0) {
            responder_ack(cmd_id, false, "unknown_cmd");
            return;
        }

        // Extraer value (true/false)
        if (!extract_json_bool(line, "value", value_bool)) {
            responder_ack(cmd_id, false, "malformed_cmd");
            return;
        }

        if (value_bool) {
#if !MODO_SIM_SIN_SENSORES
            if (sensores_get_sensor_fault()) {
                responder_ack(cmd_id, false, "sensor_fault");
                return;
            }
#if !PERMITIR_BOMBA_SIN_CALIBRAR
            if (!calibracion_esta_calibrado()) {
                responder_ack(cmd_id, false, "not_calibrated");
                return;
            }
#endif
            if (sensores_get_overflow_a()) {
                responder_ack(cmd_id, false, "overflow_a");
                return;
            }
            if (sensores_get_overflow_b()) {
                responder_ack(cmd_id, false, "overflow_b");
                return;
            }
#endif
            actuadores_set_bomba(true);
        } else {
            // Apagar siempre permitido
            actuadores_set_bomba(false);
        }

        responder_ack(cmd_id, true, nullptr);
        return;
    }

    responder_ack(ack_id, false, "unknown_cmd");
}

void protocolo_procesar_serie() {
    while (Serial.available() > 0) {
        char c = (char)Serial.read();

        if (c == '\n' || c == '\r') {
            if (s_rx_index > 0) {
                if (!s_rx_overflow) {
                    s_rx_buffer[s_rx_index] = '\0';
                    procesar_comando_linea(s_rx_buffer);
                } else {
                    // Se descartó la línea por superar el buffer estático
                    s_rx_overflow = false;
                }
                s_rx_index = 0;
            }
        } else {
            if (s_rx_index < PROTOCOL_RX_BUFFER_SIZE - 1) {
                if (!s_rx_overflow) {
                    s_rx_buffer[s_rx_index++] = c;
                }
            } else {
                // Desborde: se descarta la línea hasta encontrar un salto de línea
                s_rx_overflow = true;
            }
        }
    }
}
