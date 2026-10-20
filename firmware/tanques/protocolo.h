#ifndef PROTOCOLO_H
#define PROTOCOLO_H

#include <Arduino.h>
#include "sensores.h"

/**
 * Inicializa la interfaz serie del protocolo.
 */
void protocolo_init();

/**
 * Emite una trama periódica de telemetría formateada estrictamente bajo el contrato JSON v1.
 * Utiliza strings en memoria Flash (F()) y buffers numéricos fijos sin usar la clase String.
 */
void protocolo_emitir_telemetria(
    unsigned long seq,
    unsigned long uptime_ms,
    const LecturasSensores &sensores,
    bool bomba_estado
);

/**
 * Lee bytes del puerto serie de forma no bloqueante, detecta líneas completas,
 * previene desbordes de buffer y parsea comandos JSON entrantes.
 */
void protocolo_procesar_serie();

#endif // PROTOCOLO_H
