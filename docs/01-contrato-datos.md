# Especificación de Contrato de Datos e Interfaz Serial

**Proyecto**: Kit Didáctico de Tanques Interconectados (UTN FRSF / GITDA)  
**Canal**: UART / USB Serial (115200 baudios, 8N1)  
**Compatibilidad**: Obsidian Markdown / CommonMark

---

## 1. Principios de Comunicación

1. **Protocolo Serial**:
   - Trama orientada a líneas de texto en formato JSON terminadas por `\n` (`ASCII 0x0A` o `\r\n`).
   - Tasa de transmisión: **115200 bps**, 8 bits de datos, sin paridad, 1 bit de parada (8N1).
   - Control de reset de la placa ESP32: El host (Raspberry Pi) debe inicializar la conexión con las líneas DTR y RTS desactivadas (`dtr=False`, `rts=False` en pySerial) antes de abrir el descriptor de archivo para evitar el reinicio automático del ESP32.
2. **Sincronización Temporal**:
   - El microcontrolador ESP32 **no posee RTC** ni conexión directa a un servidor NTP.
   - El ESP32 emite el contador de tiempo de ejecución `uptime_ms`.
   - El sellado de tiempo canónico (*timestamp UTC*) lo estampa el script `edge/bridge.py` en la Raspberry Pi al momento de recibir y validar la trama antes de persistirla en InfluxDB.
3. **Topología Hidráulica y Mecánica**:
   - Dos tanques acoplados en serie: Tanque A (superior) y Tanque B (inferior/intermedio), que descargan hacia un reservorio.
   - Las secciones transversales (área en $\text{cm}^2$) de los cilindros son distintas y **no están fijas en el código**: residen en archivos de configuración (`edge/config.yaml` / `application.yml`).
   - Las válvulas de interconexión y drenaje son **manuales**. Por definición del sistema, **no existen sensores ni actuadores de válvulas** en el contrato.
4. **Delimitación Térmica**:
   - La temperatura se sensa únicamente con fines didácticos de **monitoreo pasivo**.
   - **No existen placas Peltier** ni sistemas de enfriamiento/calefacción activos en el kit.

---

## 2. Telemetría Periódica (ESP32 $\to$ Raspberry Pi)

La telemetría se emite a una tasa nominal de **1 Hz (1 trama por segundo)**.

### 2.1 Ejemplo de Trama JSON

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

### 2.2 Diccionario de Campos de Telemetría

| Campo | Tipo | Unidad | Rango / Valores | Descripción |
|---|---|---|---|---|
| `v` | Integer | - | `1` | Versión del esquema del contrato. Permite evolución hacia adelante. |
| `seq` | Integer | - | `0` a `4294967295` | Número de secuencia incremental para detectar pérdidas de tramas. |
| `uptime_ms` | Integer | ms | $\ge 0$ | Milisegundos transcurridos desde el arranque del ESP32. |
| **`tank_a`** | Object | - | - | Mediciones del Tanque A (tanque superior). |
| `tank_a.weight_g` | Float | g (gramos) | `0.0` a `5000.0` | Masa líquida neta calculada por celda de carga tarada. |
| `tank_a.level_pct` | Float | % | `0.0` a `100.0` | Nivel relativo de llenado según la capacidad máxima calibrada. |
| `tank_a.temp_c` | Float | °C | `-10.0` a `80.0` | Temperatura del fluido (sensor sumergido, solo monitoreo). |
| **`tank_b`** | Object | - | - | Mediciones del Tanque B (tanque inferior). |
| `tank_b.weight_g` | Float | g (gramos) | `0.0` a `5000.0` | Masa líquida neta calculada por celda de carga tarada. |
| `tank_b.level_pct` | Float | % | `0.0` a `100.0` | Nivel relativo de llenado según la capacidad máxima calibrada. |
| `tank_b.temp_c` | Float | °C | `-10.0` a `80.0` | Temperatura del fluido (sensor sumergido, solo monitoreo). |
| `flow_lpm` | Float | L/min | `0.0` a `10.0` | Caudal volumétrico instantáneo medido en la línea de impulsión. |
| **`actuators`** | Object | Map | Extensible | Estado de todos los actuadores del kit. |
| `actuators.pump` | Boolean | - | `true` \| `false` | Estado actual de encendido (`true`) o apagado (`false`) de la bomba. |
| **`alarms`** | Object | Map | Extensible | Banderas booleanas de fallas e interlocks activos. |
| `alarms.overflow_a` | Boolean | - | `true` \| `false` | Alarma de sobrellenado en Tanque A ($> 95\%$). Provoca corte de bomba. |
| `alarms.overflow_b` | Boolean | - | `true` \| `false` | Alarma de sobrellenado en Tanque B ($> 95\%$). Provoca corte de bomba. |
| `alarms.sensor_fault`| Boolean | - | `true` \| `false` | Fallo de lectura o desconexión física de alguno de los sensores. |
| `mode` | String | - | `"auto"` \| `"manual"` | Modo de operación actual reportado por la lógica de control. |

---

## 3. Comandos de Control (Raspberry Pi $\to$ ESP32)

Los comandos se envían a demanda cuando un usuario autorizado (`DOCENTE`) solicita modificar el estado de un actuador.

### 3.1 Estructura del Comando

```json
{
  "id": "c104",
  "cmd": "set",
  "target": "pump",
  "value": true
}
```

### 3.2 Campos del Comando

| Campo | Tipo | Obligatorio | Valores Válidos | Descripción |
|---|---|:---:|---|---|
| `id` | String | Sí | Alfanumérico (ej: `"c1"`, UUID) | Identificador de correlación para asociar la respuesta (`ack`). |
| `cmd` | String | Sí | `"set"` | Acción a ejecutar sobre el actuador. |
| `target` | String | Sí | `"pump"` *(extensible)* | Nombre del actuador destino. El software debe estar desacoplado para incorporar otros actuadores en el futuro. |
| `value` | Boolean / Variant | Sí | `true` \| `false` | Valor objetivo del actuador (para bomba: encender/apagar). |

---

## 4. Confirmación de Comando / Acknowledgment (ESP32 $\to$ Raspberry Pi)

El microcontrolador responde de forma síncrona/inmediata al procesar el comando.

### 4.1 Comando Aceptado y Ejecutado

```json
{
  "ack": "c104",
  "ok": true
}
```

### 4.2 Comando Rechazado por Interlock o Error

Si un interlock de seguridad está activo (por ejemplo, el Tanque A o Tanque B supera el 95% de nivel y se intenta encender la bomba), el microcontrolador o el simulador rechaza la orden de forma segura:

```json
{
  "ack": "c104",
  "ok": false,
  "reason": "overflow_a"
}
```

### 4.3 Razones de Rechazo Estándar (`reason`)

- `"overflow_a"`: Intento de encender la bomba cuando el nivel del Tanque A supera el umbral crítico ($>95\%$).
- `"overflow_b"`: Intento de encender la bomba cuando el nivel del Tanque B supera el umbral crítico ($>95\%$).
- `"sensor_fault"`: Interlock por fallo o lectura espuria de sensores de nivel.
- `"unknown_target"`: El actuador especificado en `target` no existe o no está registrado.
- `"invalid_command"`: Estructura de trama JSON no válida o comando no soportado.
- `"invalid_value"`: El valor suministrado no coincide con el tipo esperado por el actuador.
