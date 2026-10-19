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
