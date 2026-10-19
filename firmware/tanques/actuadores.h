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
 * @param encendida true para encender, false para apagar.
 */
void actuadores_set_bomba(bool encendida);

/**
 * Consulta el estado actual de la bomba.
 * @return true si está encendida, false si está apagada.
 */
bool actuadores_get_bomba();

#endif // ACTUADORES_H
