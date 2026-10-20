# Simulación en Wokwi (Sub-etapa 6.4)

Circuito de `diagram.json`: Arduino Uno, DS18B20 (bus en `D8` con pull-up de 4,7 kΩ a 5 V), módulo relé en `D9`, dos `wokwi-hx711` tipo `5kg` (`celdaA`: DT `D4`, SCK `D5`; `celdaB`: DT `D6`, SCK `D7`; VCC a 5 V), un `wokwi-clock-generator` a 16 Hz en `D2` que emula el caudalímetro y dos cadenas de 8 NeoPixel (`D10` Tanque A, `D11` Tanque B) con resistencia de 330 Ω en serie en cada `DIN`.

> El diagrama **no está verificado en Wokwi** (tampoco las conexiones de los `wokwi-hx711` y del `wokwi-clock-generator` agregados) (no hay `wokwi-cli` ni cuenta en el entorno donde se generó). Los tipos de componente y nombres de pines siguen la documentación pública de Wokwi; si algún pin no conecta, corregirlo desde el editor web.

## Uso (extensión Wokwi para VS Code)

1. Compilar desde la raíz del repo (la carpeta `build/` está en `.gitignore`):
   ```bash
   arduino-cli compile --fqbn arduino:avr:uno firmware/tanques --output-dir firmware/wokwi/build
   ```
2. Abrir `firmware/wokwi/` en VS Code y ejecutar "Wokwi: Start Simulator".
3. Abrir el monitor serie (115200) y enviar comandos, por ejemplo:
   ```json
   {"id":"c1","cmd":"set","target":"pump","value":true}
   {"id":"c2","cmd":"set_capacity","tank":"a","grams":4000}
   {"id":"c3","cmd":"cal_flow","pulses_per_l":450}
   ```

## Qué esperar

- Con `MODO_SIM_SIN_SENSORES 0` (valor por defecto) y los `wokwi-hx711` conectados, se espera que `is_ready()` sea verdadero y aparezcan pesos y niveles (con la escala por defecto de 420 cuentas/g y 2000 g de capacidad, las lecturas de 0 a 2100 dan 0 a 5 g, es decir 0 a 0,25 %). El encendido de la bomba se rechaza con `not_calibrated` hasta fijar tara, escala y capacidad de ambos tanques. **No verificado en Wokwi.** Si se quita un HX711 del diagrama vuelve el comportamiento anterior: `sensor_fault`, rechazo con `reason: "sensor_fault"` y último LED rojo parpadeando.
- Con el generador a 16 Hz y el factor K por defecto de 450 pulsos/L se espera un caudal de unos 2,1 L/min (cálculo propio, no verificado en Wokwi).
- Para ver conmutar el relé y el LED `D13`, poner `MODO_SIM_SIN_SENSORES` en `1` en `config.h` y recompilar. **Volver a `0` antes de cargar el firmware en el kit real.**
- Se ve la lectura del DS18B20 en `temp_c` (editable con el control del sensor en Wokwi).

## Cargar el firmware completo en un proyecto del navegador (wokwi.com)

1. Crear un proyecto "Arduino Uno" en wokwi.com.
2. Reemplazar el `diagram.json` del proyecto por el de esta carpeta.
3. Cargar **todos** los archivos de `firmware/tanques/`: `tanques.ino`, `actuadores.h/.cpp`, `calibracion.h/.cpp`, `config.h`, `indicadores.h/.cpp`, `protocolo.h/.cpp` y `sensores.h/.cpp`. El archivo principal debe ser `tanques.ino`.
4. Crear `libraries.txt` con las versiones aprobadas (nombres del Library Manager de Arduino, como en `arduino-cli`):
   ```text
   HX711 Arduino Library@0.7.5
   OneWire@2.3.8
   DallasTemperature@4.0.6
   Adafruit NeoPixel@1.15.5
   ```
5. Iniciar la simulación y abrir el monitor serie a 115200.

Estado de verificación: la documentación de Wokwi confirma que `libraries.txt` admite una librería por línea y fijar la versión con `Nombre@versión`. **No verificado**: cómo se agregan varios `.ino`/`.h`/`.cpp` al proyecto del navegador (la documentación consultada no lo describe) ni que esos nombres de librería sean los que acepta el Library Manager de Wokwi. Si alguno no resuelve, corregirlo desde el editor. El flujo con la extensión de VS Code y `arduino-cli` (sección anterior) no depende de esto.

## Limitación: la escala del HX711 no se puede calibrar en Wokwi

`cal_scale` acepta de 1 a 100000 cuentas/g (`CAL_SCALE_MIN` y `CAL_SCALE_MAX` en `calibracion.h`). La pieza `wokwi-hx711` de 5 kg entrega de 0 a 2100 cuentas (rango de la documentación de Wokwi) para 0 a 5000 g, es decir unas **0,42 cuentas/g** (2100 / 5000; con la de 50 kg, 21000 / 50000, da lo mismo). Ese valor está **por debajo del mínimo aceptado**: `cal_scale` lo rechaza con `invalid_scale` y, sin un cambio de compilación (bajar `CAL_SCALE_MIN`), no se puede calibrar la escala en el simulador. **Ese cambio NO se hace ahora**: el mínimo de 1 cuenta/g es una validación de seguridad pensada para el kit real. En Wokwi el firmware queda con la escala por defecto (420 cuentas/g), así que los pesos simulados no representan gramos reales y `not_calibrated` sigue rechazando el encendido de la bomba hasta fijar una escala; la simulación no sirve para probar esa ruta completa.

## Qué NO simula

Ver `docs/04-hardware.md`, sección 6.1: calibración física de celdas y caudalímetro reales, bomba/hidráulica y temporización eléctrica real.
