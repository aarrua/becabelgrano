#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// ==============================================================================
// Modo de Operación y Simulación
// ==============================================================================
// Si está activo, el firmware emite telemetría con valores null y sensor_fault=true,
// y conmuta el LED del pin 13 como indicador visual del actuador de bomba.
// Permite probar el firmware y la comunicación serial con el Arduino Uno solo.
#define MODO_SIM_SIN_SENSORES 1

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
// Configuración de Lógica de Actuadores
// ==============================================================================
// 1 = Relé activo en nivel ALTO (HIGH enciende, LOW apaga)
// 0 = Relé activo en nivel BAJO (LOW enciende, HIGH apaga)
#define RELE_ACTIVO_ALTO   1

// ==============================================================================
// Parámetros de Comunicación Serial y Temporización
// ==============================================================================
#define SERIAL_BAUDRATE           115200
#define SERIAL_RX_BUFFER_SIZE     96
#define TELEMETRY_INTERVAL_MS     1000

// ==============================================================================
// Parámetros Físicos y Umbrales de Seguridad
// ==============================================================================
#define OVERFLOW_THRESHOLD_PCT    85.0f

#endif // CONFIG_H
