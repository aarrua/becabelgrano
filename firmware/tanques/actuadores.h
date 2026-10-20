#ifndef ACTUADORES_H
#define ACTUADORES_H

#include <Arduino.h>

/**
 * Inicializa los pines de actuadores.
 * REGLA ESTRICTA DE SEGURIDAD: Lo primero que ejecuta es asegurar el relé
 * en estado APAGADO antes de cualquier otra operación.
 */
void actuadores_init();

/**
 * Establece el estado de encendido o apagado de la bomba de impulsión.
 * Si se enciende, reinicia el temporizador watchdog de bombeo continuo.
 * @param encendida true para encender, false para apagar.
 */
void actuadores_set_bomba(bool encendida);

/**
 * Consulta el estado actual de la bomba.
 * @return true si está encendida, false si está apagada.
 */
bool actuadores_get_bomba();

/**
 * Verifica si se superó el tiempo máximo continuo de bombeo (watchdog).
 * Si se excedió, apaga la bomba de inmediato y activa la alarma pump_timeout.
 */
void actuadores_verificar_watchdog();

/**
 * Consulta si la alarma de timeout de bomba se encuentra activa.
 * @return true si la bomba fue apagada por exceder el tiempo continuo máximo.
 */
bool actuadores_get_pump_timeout();

/**
 * Renueva el temporizador del watchdog de bomba sin modificar el estado físico.
 */
void actuadores_renovar_watchdog();

#endif // ACTUADORES_H
