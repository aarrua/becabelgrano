# Decisiones de la Etapa 6 (sub-etapas 6.3 y 6.4 y laguna de calibración)

Decisiones tomadas de forma autónoma ante ambigüedades; en cada caso se eligió la opción más segura.

1. **Rama**: el prompt indica `feature/fase-4-firmware`, pero la rama activa era `feature/fase-4-firmware-auto`. Se trabajó en la activa; no se hizo checkout, push ni merge.
2. **Rangos de calibración**: capacidad 100-10000 g (tope = capacidad de la celda de 10 kg) y factor K 10-10000 pulsos/L (cubre desde ~100 hasta YF-S401, ~5880). Se rechaza NaN con comparaciones afirmativas. Un rechazo no modifica ningún valor. Son constantes en `calibracion.h`.
3. **Nombres de campos**: `grams` y `pulses_per_l` (nombres largos para evitar colisión con el parser por subcadena, p. ej. una clave `"k"`).
4. **Bridge sin cambios de código**: ya reenvía cualquier JSON con `id`; solo se agregaron tests.
5. **Memoria dinámica en NeoPixel**: Adafruit NeoPixel reserva con `malloc` 3 bytes por LED, una sola vez, al construir el objeto (48 bytes con 2 × 8 LEDs). Se acepta porque ocurre antes de `setup()` y nunca se libera, así que no hay fragmentación; es la única excepción a "sin heap" y no está contada en el uso global de RAM medido.
6. **Cantidad de LEDs**: 8 por tira (`NEOPIXEL_LEDS_POR_TIRA`), ajustable. Brillo 20/255.
7. **Umbrales de color por temperatura**: azul < 22 °C, verde < 30 °C, ámbar < 40 °C, rojo ≥ 40 °C (constantes en `config.h`). Son valores de partida, sin base experimental.
8. **Alarma NeoPixel**: se considera alarma del tanque `overflow` de ese tanque, `sensor_fault` o `pump_timeout` (estos dos últimos son globales y encienden ambas tiras). Con alarma, el último LED queda reservado para el parpadeo rojo.
9. **Interrupciones y serie**: `show()` corta interrupciones ~250 µs por tira, lo que podría perder un byte serie o un pulso del caudalímetro. Mitigación: refrescar solo al cambiar la imagen, una tira por llamada y no refrescar con bytes pendientes en el buffer serie. No medido en hardware.
10. **Tiras desconectadas**: WS2812B es de solo escritura, no se puede detectar; se garantiza que no falla ni bloquea.
11. **Wokwi**: NeoPixel como cadenas de 8 `wokwi-neopixel` (no hay tira oficial verificada). El diagrama no se pudo abrir en Wokwi desde este entorno.
12. **Commit de `.gitignore`**: la modificación previa del `.gitignore` (ignorar `prompt-*.md`, `salida.md`, `claude/`) no es de este trabajo y no se incluyó en ningún commit.

---

# Revisión de seguridad del firmware (`prompt.md`)

Cada punto se corrigió en un commit separado. Memoria final medida: ver `docs/INFORME-6.md` y la salida de compilación entregada.

## Correcciones implementadas

1. **Fail-safe por nivel inválido** (`sensores.cpp`). Si el nivel de cualquiera de los dos tanques es inválido, se fuerza `sensor_fault = true` y se apaga la bomba si estaba encendida. Antes solo se cortaba por overflow. El corte ocurre en cada lectura de sensores (1 Hz), sin esperar comandos. Una falla transitoria de un ciclo (HX711 no listo) también corta: es lo más seguro y la bomba se reenciende a mano. La temperatura inválida **no** corta una bomba ya encendida (ver propuesta 8b), pero sí bloquea el encendido, como hasta ahora.
2. **Plausibilidad HX711**. Constantes en `config.h`: `HX711_RAW_SATURADO = 8388000` (a 607 cuentas del extremo ±8388607) y `HX711_PESO_MIN_PLAUSIBLE_G = -50 g`. Crudo saturado o peso menor al umbral → peso y nivel inválidos y `sensor_fault`. Los pesos negativos plausibles ya no se recortan; `weight_g` puede salir levemente negativo. El **nivel** sí se acota a `>= 0` para mantener el rango 0-100 % del contrato. El valor de -50 g es un punto de partida a ajustar con el kit real.
3. **Calibración obligatoria**. Capacidad por defecto 2000 g en ambos tanques (el cilindro más chico mide 2450 g), de modo que el nivel calculado con el default nunca subestima el llenado real. Flag `calibracion_esta_calibrado()`: true con EEPROM válida **o** con tara, escala y capacidad de **ambos** tanques fijadas en la sesión. Decisión propia: se exige además la **tara** (el prompt pedía escala y capacidad), porque sin tara el peso sale con el offset crudo y la escala no tiene sentido. `reset_cal` borra el estado calibrado. `save_cal` se rechaza con `not_calibrated` si no está calibrado, para que valores de fábrica guardados no pasen por "EEPROM válida" tras un reinicio. Orden de chequeos del encendido: `sensor_fault`, `not_calibrated`, `overflow_a`, `overflow_b` (sin calibración el nivel no es confiable, así que ese es el motivo útil). `PERMITIR_BOMBA_SIN_CALIBRAR` (0) omite solo este chequeo y emite un `#warning` si vale 1. Tolerancia: el bridge reenvía el ack sin tocar el motivo (test nuevo en `edge/tests/test_bridge.py`), el backend responde 409 con el `reason` (test nuevo en `BridgeActuatorGatewayTest`) y la SPA muestra un mensaje específico (`PumpControl.tsx`, verificada solo con `tsc`, sin test de UI). Contrato en `docs/01-contrato-datos.md` 4.3. Efecto colateral: tras actualizar el firmware, un kit sin EEPROM guardada queda bloqueado hasta calibrar; es lo buscado.
4. **`cal_scale` validado** con el mismo `en_rango` que los demás: `[1, 100000]` cuentas/g; rechaza NaN, infinito y negativos con `invalid_scale`. `calibracion_set_scale_a/b` ahora devuelven `bool`. Un valor inválido no modifica nada ni cuenta como calibración de sesión.
5. **`actuadores_init`**: `digitalWrite` del nivel de apagado antes de `pinMode(OUTPUT)`. En AVR, escribir sobre un pin de entrada fija el pull-up; al pasar a salida sale ya con ese nivel. Con relé activo en bajo, el orden anterior dejaba el pin en LOW un instante (pulso de encendido) en cada reset. El motivo está comentado en el código. No verificado con osciloscopio.
6. **`tare` con HX711 no listo**: responde `ok:false, reason:"sensor_not_ready"` y no cambia la tara; el crudo saturado también cuenta como no listo. En `MODO_SIM_SIN_SENSORES` siempre responde `sensor_not_ready` (antes "tareaba" 0). `sensores_get_raw_hx711_a/b` se reemplazaron por `sensores_leer_raw_a/b(long&)`, que devuelven `bool`.
7. **Ids de hasta 36 caracteres** (UUID con guiones): buffer de `id` de 37 bytes y buffer de recepción de 96 a 128 bytes. Se amplió el de recepción porque el bridge reenvía el campo `ts` y un `set` con id de 36 más `ts` mide unos 105 caracteres, que con 96 se descartaría por desborde. RAM global: 42 % (865 bytes), por debajo del 75 %. Los ids que genera hoy el backend miden 10 caracteres.

## Propuestas (NO implementadas)

### 8a. Histéresis del interlock de sobrellenado (corte 85 %, rearme bajo 80 %)
Hoy `overflow_x` se evalúa sin memoria: con el nivel oscilando alrededor de 85 % (olas, ruido de la celda, bomba que apaga y enciende) la alarma y el rechazo del encendido conmutan en cada ciclo.

Propuesta: una bandera de estado por tanque, `overflow = true` al llegar a 85 % y `false` solo cuando el nivel baja de 80 % (`OVERFLOW_REARME_PCT` en `config.h`). El encendido se rechaza mientras la bandera esté activa, incluso entre 80 y 85 %.

Impacto: cambia el firmware y conviene reflejar el parámetro en `edge/simulator.py` y `edge/config.yaml` para mantener paridad. El contrato JSON no cambia. Trade-off: el tanque debe vaciarse 5 puntos más antes de rearmar. Riesgo: una bandera pegada ante una falla de lectura; se resolvería dejando la bandera en `true` ante nivel inválido (consistente con el fail-safe del punto 1). El 80 % también debe calibrarse con el kit real junto con el umbral de 85 %.

### 8b. Que un fallo del DS18B20 no bloquee el encendido de la bomba
Hoy cualquier falla de sensor, incluida la temperatura, levanta `sensor_fault` y el firmware rechaza el encendido. La temperatura es solo monitoreo pasivo y no interviene en ninguna decisión de seguridad.

Propuesta: reservar `sensor_fault` para lo que afecta la seguridad (celdas de carga y su plausibilidad) e informar la falla de temperatura aparte (`temp_fault`, o solo con los `temp_c: null` que ya existen).

Cambio de contrato que implica:
- `alarms.sensor_fault` deja de significar "cualquier sensor": hay que redefinirlo en `docs/01-contrato-datos.md` y `docs/02-flujo-comandos.md`.
- Si se agrega `alarms.temp_fault` es una clave nueva: simulador, bridge (`format_influx_line`), InfluxDB/Grafana, DTOs y tests del backend (`TelemetryFrameSerializationTest`, `InfluxTelemetryProviderTest`, mocks) y la SPA (`TankVisualizer`, `MonitorView`) deben tolerarla. Los consumidores que hoy leen `sensor_fault` para mostrar "falla de sensores" dejarían de ver la falla de temperatura.
- El fail-safe del punto 1 no cambia (depende del nivel, no de `sensor_fault`).
- Trade-off: se puede operar con un DS18B20 roto, a costa de que nadie se entere de esa falla salvo que la SPA la muestre. Recomendación: implementarlo solo junto con un `temp_fault` visible en la SPA.
