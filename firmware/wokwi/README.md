# Simulación en Wokwi (Sub-etapa 6.4)

Circuito de `diagram.json`: Arduino Uno, DS18B20 (bus en `D8` con pull-up de 4,7 kΩ a 5 V), módulo relé en `D9` y dos cadenas de 8 NeoPixel (`D10` Tanque A, `D11` Tanque B) con resistencia de 330 Ω en serie en cada `DIN`.

> El diagrama **no está verificado en Wokwi** (no hay `wokwi-cli` ni cuenta en el entorno donde se generó). Los tipos de componente y nombres de pines siguen la documentación pública de Wokwi; si algún pin no conecta, corregirlo desde el editor web.

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

- Con `MODO_SIM_SIN_SENSORES 0` (valor por defecto), sin HX711 el firmware informa `sensor_fault`, rechaza el encendido de la bomba con `reason: "sensor_fault"` y el último LED de ambas tiras parpadea en rojo. Es el comportamiento seguro esperado.
- Para ver conmutar el relé y el LED `D13`, poner `MODO_SIM_SIN_SENSORES` en `1` en `config.h` y recompilar. **Volver a `0` antes de cargar el firmware en el kit real.**
- Se ve la lectura del DS18B20 en `temp_c` (editable con el control del sensor en Wokwi).

## Qué NO simula

Ver `docs/04-hardware.md`, sección 6.1: HX711 con celda de carga real, caudalímetro, bomba/hidráulica y temporización eléctrica real.
