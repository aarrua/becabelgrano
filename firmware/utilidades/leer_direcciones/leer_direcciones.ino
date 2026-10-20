/**
 * ==============================================================================
 * Kit Didáctico de Tanques Interconectados - UTN FRSF / GITDA
 * Utilidad: Lector de Direcciones ROM de Sensores Dallas DS18B20
 * ==============================================================================
 * Escanea el bus OneWire (Pin D8 con resistencia pull-up de 4.7 kΩ a 5V)
 * y detecta todos los sensores de temperatura DS18B20 conectados.
 * 
 * Imprime las direcciones de 64 bits formateadas directamente en sintaxis C/C++
 * para copiar y pegar en 'firmware/tanques/config.h'.
 * 
 * Velocidad Serial: 115200 bps
 * ==============================================================================
 */

#include <OneWire.h>
#include <DallasTemperature.h>

#define PIN_ONEWIRE 8

static OneWire oneWire(PIN_ONEWIRE);
static DallasTemperature sensors(&oneWire);

void printAddress(DeviceAddress deviceAddress) {
    Serial.print(F("{ "));
    for (uint8_t i = 0; i < 8; i++) {
        Serial.print(F("0x"));
        if (deviceAddress[i] < 16) Serial.print(F("0"));
        Serial.print(deviceAddress[i], HEX);
        if (i < 7) Serial.print(F(", "));
    }
    Serial.print(F(" }"));
}

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 3000); // Esperar puerto serie USB si es necesario

    Serial.println(F("\n========================================================"));
    Serial.println(F(" UTN FRSF / GITDA - Lector de Direcciones DS18B20"));
    Serial.println(F(" Bus OneWire en Pin Digital: D8 (Pull-up 4.7k a 5V)"));
    Serial.println(F("========================================================\n"));

    sensors.begin();
}

void loop() {
    Serial.println(F("Iniciando escaneo de bus OneWire..."));

    byte addr[8];
    uint8_t count = 0;

    oneWire.reset_search();

    while (oneWire.search(addr)) {
        count++;
        Serial.print(F("\n[Sensor #"));
        Serial.print(count);
        Serial.println(F(" detectado]"));

        // Validar CRC
        if (OneWire::crc8(addr, 7) != addr[7]) {
            Serial.println(F("  ADVERTENCIA: CRC inválido en este dispositivo."));
            continue;
        }

        // Validar tipo de chip
        if (addr[0] == 0x28) {
            Serial.println(F("  Tipo: Dallas DS18B20 (Genuino / Compatible)"));
        } else {
            Serial.print(F("  Tipo: Desconocido (Familia 0x"));
            Serial.print(addr[0], HEX);
            Serial.println(F(")"));
        }

        // Imprimir dirección ROM en formato C++
        Serial.print(F("  Direccion C++: "));
        printAddress(addr);
        Serial.println();

        // Leer temperatura de prueba
        sensors.requestTemperatures();
        float tempC = sensors.getTempC(addr);
        Serial.print(F("  Temperatura leida: "));
        if (tempC == DEVICE_DISCONNECTED_C) {
            Serial.println(F("ERROR (Desconectado)"));
        } else {
            Serial.print(tempC, 2);
            Serial.println(F(" °C"));
        }
    }

    Serial.println(F("\n--------------------------------------------------------"));
    if (count == 0) {
        Serial.println(F("No se detectaron dispositivos OneWire en el pin D8."));
        Serial.println(F("Verifique:"));
        Serial.println(F(" 1. Cable de datos del sensor conectado al pin D8 de Arduino."));
        Serial.println(F(" 2. Resistencia de pull-up de 4.7 kΩ entre DATA (D8) y 5V."));
        Serial.println(F(" 3. Alimentacion (VCC a 5V y GND a GND)."));
    } else {
        Serial.print(F("Total dispositivos encontrados: "));
        Serial.println(count);
        Serial.println(F("\nINSTRUCCIONES DE CONFIGURACION:"));
        Serial.println(F("1. Identifique que sensor corresponde al Tanque A y al Tanque B"));
        Serial.println(F("   (puede sujetar un sensor con la mano para ver cual aumenta su temp)."));
        Serial.println(F("2. Copie las direcciones e ingreselas en 'firmware/tanques/config.h':"));
        Serial.println(F("     #define DS18B20_ADDR_A { ... }"));
        Serial.println(F("     #define DS18B20_ADDR_B { ... }"));
        Serial.println(F("3. Cambie en 'firmware/tanques/config.h':"));
        Serial.println(F("     #define DS18B20_SON_DIRECCIONES_DE_EJEMPLO 0"));
    }
    Serial.println(F("========================================================\n"));

    Serial.println(F("Reintentando en 6 segundos (o presione ENTER para escanear ya)..."));
    unsigned long startWait = millis();
    while (millis() - startWait < 6000) {
        if (Serial.available()) {
            while (Serial.available()) Serial.read();
            break;
        }
        delay(50);
    }
}
