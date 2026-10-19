#include "protocolo.h"
#include "config.h"
#include "actuadores.h"
#include <string.h>

static char s_rx_buffer[SERIAL_RX_BUFFER_SIZE];
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

static void procesar_comando_linea(const char *line) {
    char cmd_id[20];
    char cmd_name[16];
    char target[16];
    bool value_bool = false;

    // Extraer id de comando obligatorio
    if (!extract_json_string(line, "id", cmd_id, sizeof(cmd_id))) {
        // Sin id identificable: descartar o responder con id desconocido
        responder_ack("?", false, "unknown_cmd");
        return;
    }

    // Extraer cmd ("set")
    if (!extract_json_string(line, "cmd", cmd_name, sizeof(cmd_name)) || strcmp(cmd_name, "set") != 0) {
        responder_ack(cmd_id, false, "unknown_cmd");
        return;
    }

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

    // Ejecución segura del comando
    actuadores_set_bomba(value_bool);
    responder_ack(cmd_id, true, nullptr);
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
            if (s_rx_index < SERIAL_RX_BUFFER_SIZE - 1) {
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
