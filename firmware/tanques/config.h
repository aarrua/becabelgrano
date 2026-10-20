#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// ==============================================================================
// Modo de Operación y Simulación
// ==============================================================================
// 0 = Firmware definitivo con lectura real por hardware (Etapa 6.2+).
// 1 = Modo simulación en banco sin sensores (emite nulls y permite bomba en Uno solo).
#define MODO_SIM_SIN_SENSORES 0

// ==============================================================================
// Mapa de Pines - Arduino Uno (ATmega328P)
// ==============================================================================
// NOTA: No utilizar D0 (RX) ni D1 (TX), reservados para comunicación serial USB.

// Sensores de Nivel / Celdas de Carga (HX711)
#define PIN_HX711_A_DOUT   4
#define PIN_HX711_A_SCK    5
#define PIN_HX711_B_DOUT   6
#define PIN_HX711_B_SCK    7

// Sensores de Temperatura (Bus OneWire Dallas DS18B20 común con pull-up 4.7k)
#define PIN_DS18B20        8

// Sensor de Caudal (Caudalímetro de efecto Hall con interrupción externa INT0)
#define PIN_FLOW_SENSOR    2

// Actuador de Bomba (Módulo Relé / MOSFET)
#define PIN_RELE_BOMBA     9

// Tiras de Indicación Visual LED NeoPixel (WS2812B)
#define PIN_NEOPIXEL_A     10
#define PIN_NEOPIXEL_B     11

// LED de Diagnóstico Integrado en Placa (duplica estado de la bomba)
#define PIN_LED_BUILTIN_ACTUADOR 13

// ==============================================================================
// Indicadores Visuales NeoPixel (barra de nivel por tanque)
// ==============================================================================
#define NEOPIXEL_LEDS_POR_TIRA    8     // LEDs por tira (1 tira por tanque)
#define NEOPIXEL_BRILLO           20    // 0-255. Bajo a propósito: limita corriente y deslumbramiento
#define NEOPIXEL_BLINK_MS         300   // Semiperiodo de parpadeo del LED de alarma
// Color de la barra según temperatura del tanque (monitoreo pasivo, sin control térmico)
#define NEOPIXEL_TEMP_AZUL_MAX_C  22.0f // < 22 °C  azul
#define NEOPIXEL_TEMP_VERDE_MAX_C 30.0f // < 30 °C  verde
#define NEOPIXEL_TEMP_AMBAR_MAX_C 40.0f // < 40 °C  ámbar; >= 40 °C rojo

// ==============================================================================
// Direcciones ROM de Sensores DS18B20 (Bus OneWire en pin D8)
// ==============================================================================
// Cada sensor DS18B20 tiene una dirección única de 8 bytes (64 bits).
// Para obtener las direcciones reales de los sensores conectados, ejecute el sketch:
// 'firmware/utilidades/leer_direcciones/leer_direcciones.ino'.
#define DS18B20_ADDR_A { 0x28, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x01 }
#define DS18B20_ADDR_B { 0x28, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x02 }

// Si está en 1, indica que las direcciones anteriores son de ejemplo
#define DS18B20_SON_DIRECCIONES_DE_EJEMPLO 1

#if (!MODO_SIM_SIN_SENSORES && DS18B20_SON_DIRECCIONES_DE_EJEMPLO)
#warning "ATENCIÓN: Se están utilizando direcciones DS18B20 de ejemplo. Ejecute 'firmware/utilidades/leer_direcciones/' para obtener las direcciones reales de sus sensores."
#endif

// ==============================================================================
// Plausibilidad de las Celdas de Carga (HX711)
// ==============================================================================
// El HX711 entrega 24 bits con signo (±8388607). Un valor crudo cercano a esos
// extremos indica saturación (cable cortado, celda desconectada o fuera de rango).
#define HX711_RAW_SATURADO         8388000L
// Peso mínimo creíble en gramos. Por debajo se considera lectura inválida
// (tara mal fijada, celda invertida o falla) y se levanta sensor_fault.
#define HX711_PESO_MIN_PLAUSIBLE_G (-50.0f)

// ==============================================================================
// Watchdog de Seguridad de Bomba (Tiempo Máximo de Bombeo Continuo)
// ==============================================================================
// 1 = Habilitado: apaga automáticamente la bomba si permanece encendida
//     más de PUMP_MAX_RUNTIME_MS continuos sin nuevos comandos recibidos.
// 0 = Deshabilitado.
#define WATCHDOG_BOMBA_HABILITADO 1
#define PUMP_MAX_RUNTIME_MS       60000UL // 60 segundos por defecto

// ==============================================================================
// Configuración de Lógica de Actuadores
// ==============================================================================
// 1 = Relé activo en nivel ALTO (HIGH enciende, LOW apaga)
// 0 = Relé activo en nivel BAJO (LOW enciende, HIGH apaga)
#define RELE_ACTIVO_ALTO   1

// ==============================================================================
// Parámetros de Comunicación Serial y Temporización
// ==============================================================================
#define SERIAL_BAUDRATE           115200
#define PROTOCOL_RX_BUFFER_SIZE   96
#define TELEMETRY_INTERVAL_MS     1000

// ==============================================================================
// Parámetros Físicos y Umbrales de Seguridad
// ==============================================================================
#define OVERFLOW_THRESHOLD_PCT    85.0f

#endif // CONFIG_H
