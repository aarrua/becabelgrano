# Firmware Arduino Uno - Kit Didáctico de Tanques Interconectados (UTN FRSF / GITDA)

Este directorio contiene la especificación y el código fuente del firmware para el microcontrolador Arduino Uno (ATmega328P) del kit didáctico.

> **Estado actual**: Especificación de contrato y requerimientos para el desarrollo de hardware/firmware. La fase inicial del proyecto utiliza un simulador software (`edge/simulator.py`) que respeta rigurosamente este contrato.

---

## 1. Responsabilidades del Arduino Uno

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

## 2. Parámetros de Comunicación Serial

- **Baudrate**: `115200`
- **Data bits**: `8`
- **Parity**: `None`
- **Stop bits**: `1`
- **Control de flujo**: Ninguno por hardware.
- **Prevención de Reset**: En la Raspberry Pi, el driver `edge/bridge.py` configura `DTR=False` y `RTS=False` antes de abrir el puerto serial para evitar el reinicio automático del Arduino Uno provocado por la conmutación de la línea DTR acoplada capacitivamente al pin RESET del ATmega328P.

---

## 3. Contrato de Datos

### 3.1 Telemetría (Arduino Uno $\to$ Raspberry Pi)

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
    "sensor_fault": false
  },
  "mode": "auto"
}
```

### 3.2 Comandos de Control (Raspberry Pi $\to$ Arduino Uno)

```json
{"id": "c1", "cmd": "set", "target": "pump", "value": true}
```

### 3.3 Confirmación / Rechazo de Comando (Arduino Uno $\to$ Raspberry Pi)

```json
{"ack": "c1", "ok": true}
```

O en caso de fallo/interlock activo:

```json
{"ack": "c1", "ok": false, "reason": "overflow_a"}
```

---

## 4. Consideraciones Físicas y de Alcance

1. **RTC**: El Arduino Uno no cuenta con reloj de tiempo real (RTC). El sellado de tiempo (*timestamping*) lo realiza la Raspberry Pi al momento de recibir la trama e ingresarla a InfluxDB.
2. **Válvulas**: Las llaves de paso entre tanques y drenajes son manuales. No existen actuadores ni sensores de estado de válvulas en el protocolo.
3. **Temperatura**: Las lecturas térmicas son puramente de **monitoreo**. No existen placas Peltier ni elementos calefactores/refrigerantes en el sistema (fuera de alcance deliberadamente).
