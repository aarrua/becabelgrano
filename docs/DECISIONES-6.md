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

## Propuestas aprobadas e implementadas

### 8a. Histéresis del interlock de sobrellenado (corte 85 %, rearme bajo 80 %)
Implementada tal como se propuso: una bandera por tanque que se activa al llegar a 85 % y se desactiva solo bajo 80 % (`OVERFLOW_REARME_PCT`). Entre 80 y 85 % conserva el estado y el encendido sigue rechazado. Decisiones de implementación:
- **Nivel inválido deja la bandera en `true`**, por lo que `alarms.overflow_x` también se levanta ante una falla de la celda (además de `sensor_fault`). La alarma NeoPixel y el rechazo `overflow_x` reflejan eso.
- **Arranque**: las banderas inician en `true` y se resuelven con la primera lectura válida. Un kit que arranca con un tanque entre 80 y 85 % queda bloqueado hasta bajar de 80 %; es lo conservador.
- **Paridad**: `edge/simulator.py` (`update_overflow_flag`, `interlocks.overflow_rearm_pct`) y `MockTelemetryProvider` (`tanques.interlocks.overflow-rearm-pct`) usan la misma regla; el rearme se acota al umbral para que la histéresis nunca sea negativa. El contrato JSON no cambia.
- **Verificación**: tests en `edge/test_edge.py` y `MockTelemetryProviderTest`. El firmware no tiene arnés de tests en este repo, así que su lógica solo se verificó compilando.
- Pendiente: calibrar el 80 % junto con el 85 % con el kit real. El simulador y el mock tienen la bomba apagada por el corte, así que la histéresis no cambia los picos medidos del ciclo de bombeo.

### 8b. La temperatura no cuenta para `sensor_fault` (versión sin campo nuevo)
Implementada sin `temp_fault`: la falla del DS18B20 se informa solo con `temp_c: null`. Consecuencias:
- `sensor_fault` significa "falla de celdas de carga o de su plausibilidad". Contrato y flujo de comandos actualizados.
- El fail-safe por nivel inválido no cambia (depende del nivel).
- Verificado que la alarma NeoPixel (`indicadores.cpp`) usa `overflow`, `sensor_fault` y `pump_timeout` sin asumir temperatura, y que la barra queda gris ante temperatura inválida. En la SPA, `TankVisualizer` ya mostraba `--` ante `temp_c` nulo; se ajustaron los textos de `MonitorView` y `PumpControl` que hablaban de "sensores" en general.
- **Riesgo aceptado**: se puede operar con un DS18B20 roto y la SPA solo lo muestra como `--` en la temperatura, sin alerta propia. Si se necesita visibilidad, agregar `temp_fault` (cambio de contrato; ver la lista de consumidores en la propuesta original).
- `MODO_SIM_SIN_SENSORES` no cambia: sigue emitiendo todo `null` y `sensor_fault: true`.

### `tare` con promedio de muestras
Promedia `HX711_TARE_MUESTRAS` (10) lecturas con un tope de `HX711_TARE_TIMEOUT_MS` (2000 ms) en total. Una muestra no lista a tiempo o saturada rechaza con `sensor_not_ready` y no cambia la tara. El loop queda bloqueado ese lapso (hasta ~1 s con el HX711 a 10 Hz, ~125 ms a 80 Hz): durante ese tiempo no hay telemetría ni watchdog de bomba, y el buffer serie de 64 bytes del Uno podría desbordarse si llegan comandos. Es aceptable porque la tara se hace con el sistema en reposo. El tope se subió luego de 1,1 s a 2 s para dar margen a un HX711 a 10 Hz. `tare` se rechaza además con `pump_on` si la bomba está encendida (se chequea antes de leer el HX711). No verificado con hardware real.

## Crudo 0 / -1 del HX711 es lectura inválida (fix `hx711-ausente`)
**Hallazgo (Uno real, sin celdas ni HX711)**: la telemetría informaba `weight_g 0.0` y `level_pct 0.0` como válidos con `sensor_fault false`. La línea DOUT queda atascada en bajo, el crudo es exactamente `0` (todos los bits en cero) y pasaba los chequeos de saturación y de plausibilidad de peso (con tara 0 el peso resultante era 0 g).

**Decisión**: en `leer_celda` y `promediar_raw` (`sensores.cpp`), un crudo igual a `0` o `-1` (todos los bits en cero o en uno: módulo ausente, sin alimentar o DOUT atascado) se descarta como inválido. Constantes `HX711_RAW_TODO_CEROS` y `HX711_RAW_TODO_UNOS` en `config.h`. El efecto es `null` en peso y nivel, `sensor_fault true`, `tare` con `sensor_not_ready` y encendido de bomba rechazado con `sensor_fault`.

**Riesgo aceptado**: una celda real que entregue justo 0 o -1 en una muestra se descarta ese ciclo (un `sensor_fault` momentáneo, fail-safe). Es muy improbable y se recupera solo con la lectura siguiente. Con la celda sin carga y tara recién hecha el crudo real no es 0 salvo coincidencia exacta.

Consumo compilado (`arduino-cli`, `MODO_SIM_SIN_SENSORES 0`): Flash 17870 bytes (55%), RAM 875 bytes (42%) (con el pull-up de DOUT). Caso de prueba: `firmware/GUIA_PRUEBAS_HARDWARE.md`, caso 7.9. No verificado aún en hardware tras el cambio.

### Causa raíz del DOUT flotante: error de HX711 0.7.5
La librería HX711 0.7.5 usa `#ifdef ARCH_ESPRESSIF` (macro siempre definida) donde debía ir `#if`, y en AVR deja el pin DOUT como `INPUT` sin pull-up (la rama principal ya usa `#if`). Un DOUT flotante puede leer bajo (ceros) o ruido, lo que explica el crudo `0` del hallazgo anterior.

**Decisión**: se mantiene fijada la versión 0.7.5 y el firmware lo compensa con `pinMode(PIN_HX711_A_DOUT, INPUT_PULLUP)` y `pinMode(PIN_HX711_B_DOUT, INPUT_PULLUP)` justo después de los `begin()` en `sensores_init()`. Con el módulo conectado el HX711 maneja la línea activamente y el pull-up no molesta. El descarte de crudo `0`/`-1` se conserva como segunda defensa (módulo sin alimentar o línea atascada). No verificado en hardware tras el cambio.
