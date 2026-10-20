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
