# Firmware Arduino Uno - Kit Didáctico de Tanques Interconectados (UTN FRSF / GITDA)

Este directorio contiene la especificación y el código fuente del firmware para el microcontrolador Arduino Uno (ATmega328P) del kit didáctico.

> **Estado actual**: Firmware implementado en `firmware/tanques/` para Arduino Uno (ATmega328P). Implementación modular sin memoria dinámica (`malloc`), sin la clase `String` y sin `ArduinoJson` para máxima estabilidad y bajo consumo de RAM (**32%**) y Flash (**45%**).
> Sub-etapa 6.2 completada: soporte de sensores físicos, interlocks de seguridad, watchdog de bomba (60 s), persistencia en EEPROM bajo comando explícito `{"cmd":"save_cal"}`, sketch auxiliar de escaneo DS18B20 y guía de pruebas para armado de hardware.

---

## 1. Estructura del Código Fuente

### 1.1 Firmware Principal (`firmware/tanques/`)
- **`tanques.ino`**: Sketch principal, orquestación del ciclo no bloqueante `setup()` y `loop()` con `millis()`.
- **`config.h`**: Definición de pines (HX711, DS18B20, caudalímetro D2, relé D9, NeoPixels D10/D11), baudrate (115200), watchdog (60 s) y configuración de simulación (`MODO_SIM_SIN_SENSORES`).
- **`actuadores.h` / `actuadores.cpp`**: Control del relé de la bomba y LED de diagnóstico (pin 13). Apagado garantizado en `setup()` y watchdog de tiempo máximo continuo (60 s).
- **`sensores.h` / `sensores.cpp`**: Adquisición de variables físicas (HX711, DallasTemperature no bloqueante, caudal por interrupciones INT0) e interlocks locales.
- **`calibracion.h` / `calibracion.cpp`**: Parámetros de tara y escala en RAM con persistencia en EEPROM bajo comando explícito `{"cmd":"save_cal"}` y verificación por checksum.
- **`protocolo.h` / `protocolo.cpp`**: Parser serial de comandos entrantes con buffer fijo de descarte seguro, comandos de calibración y formateador de telemetría periódica JSON v1 en Flash.

### 1.2 Utilidades y Documentación de Puesta en Marcha
- **`firmware/utilidades/leer_direcciones/leer_direcciones.ino`**: Sketch auxiliar para escanear el bus OneWire (pin D8), obtener las direcciones ROM de 64 bits de los DS18B20 e imprimirlas formateadas para `config.h`.
- **`firmware/GUIA_PRUEBAS_HARDWARE.md`**: Guía paso a paso por componente (relé, DS18B20, HX711 con tara/escala/EEPROM, caudalímetro, interlocks) con salidas esperadas en el monitor serie para quien arme la electrónica.

---

## 2. Entorno, Core AVR y Librerías Aprobadas

### 2.1 Core de Microcontrolador
- **Core AVR**: `arduino:avr` versión `1.8.8` (Arduino AVR Boards).
```powershell
arduino-cli core install arduino:avr@1.8.8
```

### 2.2 Librerías Homologadas y Versiones Fijadas
Para garantizar determinismo en el consumo de RAM/Flash y compatibilidad binaria, se fijan las siguientes versiones aprobadas:
- **HX711**: `0.7.5` (`HX711 Arduino Library` de Bogdan Necula / Rob Tillaart)
- **OneWire**: `2.3.8` (de Paul Stoffregen / Jim Studt)
- **DallasTemperature**: `4.0.6` (de Miles Burton)
- **Adafruit NeoPixel**: `1.15.5` (de Adafruit)

Comandos exactos de instalación con `arduino-cli`:
```powershell
arduino-cli lib install "HX711 Arduino Library@0.7.5"
arduino-cli lib install "OneWire@2.3.8"
arduino-cli lib install "DallasTemperature@4.0.6"
arduino-cli lib install "Adafruit NeoPixel@1.15.5"
```

---

## 3. Compilación y Carga con Arduino CLI

Para compilar el sketch para Arduino Uno:
```powershell
& "C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" compile --fqbn arduino:avr:uno firmware/tanques
```

Para subir el firmware al Arduino Uno (por ejemplo en el puerto `COM5`):
```powershell
& "C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" upload -p COM5 --fqbn arduino:avr:uno firmware/tanques
```

---

## 4. Responsabilidades del Arduino Uno

1. **Lectura de sensores (frecuencia ~1 Hz)**:
   - Celda de carga / peso de Tanque A (`weight_g`) y cálculo de nivel (`level_pct`).
   - Celda de carga / peso de Tanque B (`weight_g`) y cálculo de nivel (`level_pct`).
   - Sensor de temperatura Tanque A (`temp_c`) y Tanque B (`temp_c`).
   - Sensor de caudal en línea (`flow_lpm`).
2. **Control de actuadores**:
   - Conmutación de relé/MOSFET para la bomba de recirculación (`actuators.pump`).
   - Diseño extensible: arquitectura modular para admitir futuros actuadores sin romper el esquema.
3. **Interlocks de seguridad por hardware/firmware**:
   - Apagado automático preventivo de la bomba ante nivel crítico (>95%) en Tanque A o Tanque B (`overflow_a` / `overflow_b`).
   - Detección de fallas en sensores (`sensor_fault`).
   - Rechazo de comandos que violen condiciones seguras.
4. **Comunicación Serial**:
   - Emisión periódica de tramas de telemetría por puerto UART/USB (115200 bps, 8N1, 1 línea JSON por trama terminada en `\n`).
   - Recepción de comandos JSON por UART/USB y respuesta de confirmación (`ack`).

---

## 5. Parámetros de Comunicación Serial

- **Baudrate**: `115200`
- **Data bits**: `8`
- **Parity**: `None`
- **Stop bits**: `1`
- **Control de flujo**: Ninguno por hardware.
- **Prevención de Reset**: En la Raspberry Pi, el driver `edge/bridge.py` configura `DTR=False` y `RTS=False` antes de abrir el puerto serial para evitar el reinicio automático del Arduino Uno provocado por la conmutación de la línea DTR acoplada capacitivamente al pin RESET del ATmega328P.

---

## 6. Contrato de Datos y Procesamiento de Comandos

### 6.1 Telemetría (Arduino Uno $\to$ Raspberry Pi)

Cada segundo se envía una trama JSON en una única línea terminada en salto de línea (`\n`):

```json
{
  "v": 1,
  "seq": 1042,
  "uptime_ms": 523411,
  "tank_a": {
    "weight_g": 1180.4,
    "level_pct": 42.5,
    "temp_c": 23.4
  },
  "tank_b": {
    "weight_g": 601.0,
    "level_pct": 18.2,
    "temp_c": 23.1
  },
  "flow_lpm": 1.8,
  "actuators": {
    "pump": true
  },
  "alarms": {
    "overflow_a": false,
    "overflow_b": false,
    "sensor_fault": false,
    "pump_timeout": false
  },
  "mode": "auto"
}
```

### 6.2 Comandos Soportados (Raspberry Pi $\to$ Arduino Uno)

1. **Control de actuadores (bomba)**:
   ```json
   {"id": "c1", "cmd": "set", "target": "pump", "value": true}
   ```
2. **Tara de celdas de carga en RAM**:
   ```json
   {"cmd": "tare", "tank": "a"}
   ```
3. **Calibración de factor de escala en RAM**:
   ```json
   {"cmd": "cal_scale", "tank": "a", "scale": 415.8}
   ```
4. **Restaurar valores de calibración por defecto en RAM**:
   ```json
   {"cmd": "reset_cal"}
   ```
5. **Persistir calibración en EEPROM**:
   ```json
   {"cmd": "save_cal"}
   ```

### 6.3 Manejo de Campos Faltantes y Claves Adicionales (`ts`)

El parser de comandos implementado en `protocolo.cpp` opera con buffers estáticos sin memoria dinámica:
1. **Claves adicionales o ignoradas (ej. `"ts"`)**:
   El backend y el bridge pueden inyectar un campo `"ts"` (timestamp en epoch ms). Dado que el Arduino Uno no dispone de RTC de hardware, la expiración temporal del comando es validada previamente en el borde por `edge/bridge.py`. El firmware busca únicamente las claves necesarias (`"id"`, `"cmd"`, `"target"`, `"value"`) e ignora en silencio cualquier campo adicional como `"ts"`, procesando el comando normalmente.
2. **Campos faltantes o inválidos**:
   - **Falta `"id"`**: Si el JSON carece de la clave `"id"` identificable, el firmware responde con id comodín:
     ```json
     {"ack":"?","ok":false,"reason":"unknown_cmd"}
     ```
   - **Falta `"cmd"` o comando desconocido**: Si `"cmd"` falta o no es `"set"`:
     ```json
     {"ack":"<id>","ok":false,"reason":"unknown_cmd"}
     ```
   - **Falta `"target"` o actuador no soportado**: Si `"target"` falta o no es `"pump"`:
     ```json
     {"ack":"<id>","ok":false,"reason":"unknown_cmd"}
     ```
   - **Falta `"value"` o valor no booleano**: Si `"value"` falta o no coincide con los literales `true` o `false`:
     ```json
     {"ack":"<id>","ok":false,"reason":"malformed_cmd"}
     ```

### 6.4 Confirmación / Rechazo de Comando (Arduino Uno $\to$ Raspberry Pi)

Respuesta exitosa:
```json
{"ack": "c1", "ok": true}
```

Respuesta ante rechazo o condición de interlock:
```json
{"ack": "c1", "ok": false, "reason": "overflow_a"}
```

---

## 7. Modo de Simulación sin Sensores (`MODO_SIM_SIN_SENSORES`)

La constante se define en `firmware/tanques/config.h`. **El valor por defecto del repositorio es `0`** (firmware definitivo con sensores reales).

### 7.1 Cómo activar el modo para probar el Uno solo

1. Abrir `firmware/tanques/config.h` y cambiar:
   ```c
   #define MODO_SIM_SIN_SENSORES 1
   ```
2. Volver a compilar y cargar el sketch en el Arduino Uno (por ejemplo con `arduino-cli compile` y `arduino-cli upload`, o desde el Arduino IDE). La constante se resuelve en tiempo de compilación, por lo que **no se puede cambiar en caliente**.
3. Con el Uno conectado solo por USB, enviar comandos por el Monitor Serie (115200 baud) o a través del bridge.
4. Al terminar, **volver a `0`** y recargar el sketch antes de cablear sensores o conectar la bomba.

Comportamiento con `MODO_SIM_SIN_SENSORES 1`:

- Todas las lecturas de tanques, temperatura y caudal se reportan como `null`, y `sensor_fault` es `true`.
- Como **excepción exclusiva para pruebas de banco**, el firmware acepta el encendido de la bomba (conmuta el pin D9 y el LED integrado del pin 13) aunque `sensor_fault` sea `true`. Sirve para validar la cadena serie $\to$ bridge $\to$ MQTT $\to$ backend.
- Los interlocks por sensores (`sensor_fault`, `overflow_a`, `overflow_b`) quedan **deshabilitados**. Nunca usar este modo con la bomba real conectada.

### 7.2 Comportamiento con `MODO_SIM_SIN_SENSORES 0`

Con `0`, el firmware lee los sensores físicos y aplica interlocks estrictos. Si el Uno se prueba solo, **sin los sensores conectados**, los HX711 no responden y los DS18B20 no se detectan, por lo que `sensor_fault` queda en `true`. **Todo intento de encendido (`value: true`) se rechaza** de inmediato con:

```json
{"ack":"<id>","ok":false,"reason":"sensor_fault"}
```

El comando de apagado (`value: false`) siempre se acepta por seguridad física. Este rechazo no es un error: es el comportamiento esperado e indica que el interlock funciona.

Con `0` y sensores conectados, antes de usar la bomba real hay que completar la calibración obligatoria de `firmware/GUIA_PRUEBAS_HARDWARE.md` (sección 1.1).

---

## 8. Consideraciones Físicas y de Alcance

1. **RTC**: El Arduino Uno no cuenta con reloj de tiempo real (RTC). El sellado de tiempo (*timestamping*) lo realiza la Raspberry Pi al momento de recibir la trama e ingresarla a InfluxDB.
2. **Válvulas**: Las llaves de paso entre tanques y drenajes son manuales. No existen actuadores ni sensores de estado de válvulas en el protocolo.
3. **Temperatura**: Las lecturas térmicas son puramente de **monitoreo**. No existen placas Peltier ni elementos calefactores/refrigerantes en el sistema (fuera de alcance deliberadamente).
