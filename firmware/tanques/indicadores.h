#ifndef INDICADORES_H
#define INDICADORES_H

#include <Arduino.h>
#include "sensores.h"

/**
 * Inicializa las tiras NeoPixel (D10 = tanque A, D11 = tanque B) apagadas.
 * Las tiras WS2812B son de solo escritura: si no están conectadas no hay
 * forma de detectarlo ni se produce ningún error; los datos simplemente se pierden.
 */
void indicadores_init();

/**
 * Actualiza las barras de nivel. No bloqueante: refresca como máximo una tira
 * por llamada y solo cuando su imagen cambió (show() deshabilita interrupciones
 * unos cientos de microsegundos).
 *  - LEDs encendidos proporcionales a level_pct; color según temperatura.
 *  - Con alarma de la tira (overflow, sensor_fault o pump_timeout) el último
 *    LED parpadea en rojo.
 * @param lecturas      Últimas lecturas de sensores.
 * @param pump_timeout  true si el watchdog de bomba apagó la bomba.
 */
void indicadores_actualizar(const LecturasSensores &lecturas, bool pump_timeout);

#endif // INDICADORES_H
