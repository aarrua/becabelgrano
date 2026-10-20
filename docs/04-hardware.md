# Especificación de Hardware y Mapa de Pines (Arduino Uno)

Este documento detalla la asignación de pines, conexiones eléctricas, requerimientos de alimentación e interlocks de hardware para el kit didáctico de tanques interconectados (UTN FRSF / GITDA).

---

## 1. Plataforma del Microcontrolador

- **Placa**: Arduino Uno R3.
- **Microcontrolador**: ATmega328P.
- **Voltaje de Operación Lógica**: 5 V DC.
- **Frecuencia de Reloj**: 16 MHz.
- **Memoria SRAM**: 2048 bytes (2 KB).
  - *Límite de diseño estricto*: $\le 75\%$ de uso estático ($\le 1536$ bytes).
  - *Prohibición de memoria dinámica*: No se utiliza `malloc`, `new`, la clase `String` ni librerías con buffers dinámicos para evitar fragmentación del heap.
- **Memoria Flash**: 32256 bytes (~32 KB).
  - *Límite de diseño estricto*: $\le 80\%$ de ocupación ($\le 25804$ bytes).
- **Comunicación con Raspberry Pi**: UART / USB Serial a **115200 bps** (8N1).
  - Pines `D0` (RX) y `D1` (TX) dedicados con exclusividad a la comunicación serie.

---

## 2. Mapa de Pines de Entrada / Salida

| Pin Arduino | Tipo | Periférico / Sensor | Conexión / Función | Notas Eléctricas |
| :---: | :---: | :--- | :--- | :--- |
| **`D0`** | RX | USB Serial | Recepción desde Raspberry Pi | Reservado para UART (115200 bps). No usar en circuito externo. |
| **`D1`** | TX | USB Serial | Transmisión hacia Raspberry Pi | Reservado para UART (115200 bps). No usar en circuito externo. |
| **`D2`** | Entrada Digital | Caudalímetro en línea | Entrada de pulsos volumétricos | Interrupción por hardware `INT0`. Configurar con `INPUT_PULLUP`. |
| **`D4`** | Entrada Digital | HX711 Tanque A | DOUT (Línea de datos) | Celda de carga 10 kg Tanque A. |
| **`D5`** | Salida Digital | HX711 Tanque A | SCK (Línea de pulsos de reloj) | Control de lectura síncrona. |
| **`D6`** | Entrada Digital | HX711 Tanque B | DOUT (Línea de datos) | Celda de carga 10 kg Tanque B. |
| **`D7`** | Salida Digital | HX711 Tanque B | SCK (Línea de pulsos de reloj) | Control de lectura síncrona. |
| **`D8`** | Bidireccional | Sensores DS18B20 | Bus OneWire común (Tanque A y B) | Requiere resistencia pull-up externa de **4.7 kΩ** a +5 V. |
| **`D9`** | Salida Digital | Módulo Relé Bomba | Disparo de conmutación de bomba | Configurable mediante `RELE_ACTIVO_ALTO` (1 o 0). Forzado a apagado en `setup()`. |
| **`D10`** | Salida Digital | Tira NeoPixel Tanque A | DIN (Datos serie WS2812B) | Resistencia de **330 Ω** a 470 Ω en serie recomendada. |
| **`D11`** | Salida Digital | Tira NeoPixel Tanque B | DIN (Datos serie WS2812B) | Resistencia de **330 Ω** a 470 Ω en serie recomendada. |
| **`D13`** | Salida Digital | LED Builtin | Indicador visual de actuador | Duplica el estado de la bomba en banco de pruebas sin relé conectado. |

---

## 3. Topología de Alimentación y Masas (GND Común)

> ⚠️ **REGLA CRÍTICA DE ALIMENTACIÓN**:  
> El microcontrolador Arduino Uno **NO debe alimentar actuadores inductivos (bomba, relé) ni tiras LED de potencia** desde el pin de 5 V de la placa, ya que los picos de corriente provocarán caídas de tensión y reinicios inesperados del microcontrolador.

1. **Fuente de Alimentación Externa (5 V DC)**:
   - Se requiere una fuente conmutada de 5 V (mínimo 2 A a 3 A según potencia de la bomba y cantidad de LEDs).
   - Alimenta directamente:
     - Módulo de relé / transistor de conmutación.
     - Bomba de agua sumergible de 5 V.
     - Líneas VCC (+5 V) de las tiras NeoPixel WS2812B.
2. **Masa Común (GND)**:
   - Es obligatorio unir el `GND` de la fuente externa de 5 V con el pin `GND` del Arduino Uno.
3. **Protección de Tiras NeoPixel**:
   - Conectar un capacitor electrolítico de **1000 µF / 16 V** entre +5 V y GND lo más cerca posible del inicio de la tira.
   - Resistencia en serie de **330 Ω** entre los pines `D10`/`D11` y la entrada `DIN` de cada tira para amortiguar transitorios de alta frecuencia.

---

## 4. Modo de Simulación en Banco (`MODO_SIM_SIN_SENSORES`)

Para facilitar el desarrollo, integración y verificación en banco sin necesidad de conectar sensores físicos:
- La macro `#define MODO_SIM_SIN_SENSORES 1` en `firmware/tanques/config.h` permite operar el firmware con la placa Arduino Uno conectada únicamente por su cable USB a la computadora.
- Se emite una trama por segundo con `sensor_fault = true` y valores nulos (`null`).
- El LED integrado (`D13`) se enciende y apaga sincronizado con los comandos seriales `{"id":"...","cmd":"set","target":"pump","value":true|false}`.

---

## 5. Indicadores NeoPixel (Sub-etapa 6.3)

Cada tanque tiene una tira WS2812B de `NEOPIXEL_LEDS_POR_TIRA` LEDs (8 por defecto): `D10` para el Tanque A y `D11` para el Tanque B. Implementación en `firmware/tanques/indicadores.cpp`; constantes en `config.h`.

### 5.1 Comportamiento

| Elemento | Regla |
| :--- | :--- |
| Barra de nivel | LEDs encendidos = `level_pct / 100 × LEDs`, redondeado. Sin nivel válido, ninguno. |
| Color | Por temperatura del tanque: azul `< 22 °C`, verde `< 30 °C`, ámbar `< 40 °C`, rojo `>= 40 °C`; gris tenue si no hay lectura. Es solo monitoreo pasivo. |
| Alarma | Si hay `overflow` del tanque, `sensor_fault` o `pump_timeout`, el **último LED parpadea en rojo** (`NEOPIXEL_BLINK_MS`) y la barra de nivel se limita a los LEDs restantes. |
| Brillo | `NEOPIXEL_BRILLO` (20 de 255), constante, para limitar la corriente y el deslumbramiento. |
| Tiras desconectadas | Sin efecto: el protocolo WS2812B es de solo escritura, no hay detección ni error; el firmware sigue operando normalmente. |

El refresco es no bloqueante: `show()` se llama solo cuando cambia la imagen y a lo sumo para una tira por iteración de `loop()`. `show()` deshabilita interrupciones unos 250 µs por tira; por eso no se refresca mientras haya bytes pendientes en el puerto serie.

### 5.2 Alimentación y cableado (obligatorio)

- **Alimentación externa de 5 V** para el `VCC` de las tiras. No tomar la corriente del pin `5V` del Arduino. Cada LED consume hasta ~60 mA a pleno blanco; con el brillo configurado el consumo real es mucho menor, pero la fuente debe dimensionarse para el peor caso.
- **GND común**: unir el `GND` de la fuente de 5 V, el `GND` del Arduino y el `GND` de las tiras. Sin masa común la señal de datos no es interpretada.
- **Resistencia de 330 Ω** en serie entre el pin (`D10` / `D11`) y `DIN` de cada tira, lo más cerca posible de la tira.
- **Capacitor de 1000 µF (≥ 6,3 V; 16 V recomendado)** entre `+5 V` y `GND`, en el inicio de la tira, para absorber el pico de encendido.
- Energizar la fuente de las tiras antes o a la vez que el Arduino, o conectar `GND` primero, para no alimentar la tira por la línea de datos.

---

## 6. Simulación en Wokwi (Sub-etapa 6.4)

Archivos en `firmware/wokwi/`: `diagram.json` (Uno, DS18B20 con resistencia pull-up de 4,7 kΩ, relé, NeoPixel, dos `wokwi-hx711` y un `wokwi-clock-generator` como caudalímetro) y `wokwi.toml`. Sirve para revisar la lógica de comandos, el relé, la alarma de watchdog y las barras NeoPixel sin hardware. Ver `firmware/wokwi/README.md`.

### 6.1 Qué simula y qué NO simula Wokwi

Cada ítem indica si se **verificó en la documentación de Wokwi** (docs.wokwi.com, consultada al redactar esto) o si **no está verificado**. Nada de esto se probó abriendo Wokwi.

- **HX711 y celdas de carga**: Wokwi tiene la pieza `wokwi-hx711` (*verificado en la documentación*). Admite `type` `"5kg"`, `"50kg"` (por defecto) y `"gauge"`, se alimenta con VCC a 5 V, expone `DT` y `SCK` y entrega lecturas crudas de 0 a 2100 (`5kg`) y de 0 a 21000 (`50kg`); la carga se fija en kg desde la simulación. La página aclara que el chip no implementa el canal B ni las ganancias 32/64. El diagrama usa dos piezas `5kg`. **No verificado**: que la librería `HX711 0.7.5` del firmware funcione con la pieza (lo esperable es que sí) y que el rango de 0 a 2100 no dispare la plausibilidad. Ver la limitación de la escala en `firmware/wokwi/README.md`: la pieza no reproduce las cuentas/g del kit real, así que no valida la calibración física, la capacidad ni los interlocks con el kit.
- **Caudalímetro de efecto Hall**: Wokwi no tiene una pieza propia (*verificado*: no figura en la lista de hardware soportado). Se emula con `wokwi-clock-generator` (existe, *verificado*; atributo `frequency`, pin `CLK`) conectado a `D2`. Que la documentación proponga el generador como fuente de pulsos para un caudalímetro **no está verificado**: es una decisión de este proyecto. Con 16 Hz y el factor K por defecto (450 pulsos/L) el firmware debería informar unos 2,1 L/min (cálculo propio, no verificado en Wokwi). Eso no valida el factor K del sensor real.
- **Bomba y circuito hidráulico**: el relé solo conmuta un LED/indicador, no hay dinámica de tanques (no hay pieza de Wokwi que la modele; *no verificado*).
- **Temporización eléctrica real** (ruido, caída de tensión, corriente de las tiras, pérdida de bytes seriales durante `show()`): *no verificado*; no se espera que se modele.
- **Dirección ROM del DS18B20 real**: el firmware usa direcciones de ejemplo y recurre a la lectura por índice, que es lo que funciona en Wokwi.

