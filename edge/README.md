# Edge Computing: Simulador Físico y Bridge Bidireccional Serial/MQTT (UTN FRSF / GITDA)

Este directorio contiene los componentes que corren en el nodo de borde (*Edge Node* en Raspberry Pi) encargados de:
1. La ingesta continua de telemetría física o simulada hacia InfluxDB 2.x con sellado de tiempo de recepción oficial.
2. El canal bidireccional de control entre el Backend (vía Mosquitto MQTT) y el microcontrolador (vía Serial USB o stdin del simulador).
3. La simulación de dinámica física e hidráulica de los tanques interconectados para experimentación en desarrollo.

---

## 1. Versión de Python y Dependencias Fijadas (Raspberry Pi 2)

- **Versión mínima de Python**: **Python 3.9+** (compatible con Python 3.9, 3.10, 3.11, 3.12, 3.13 y 3.14). Se evita toda sintaxis exclusiva de versiones posteriores a 3.9 (como uniones PEP 604 `|` en firmas o tipos genéricos built-in no subscriptables en 3.9).
- Las dependencias en `edge/requirements.txt` están fijadas a versiones exactas verificadas:

```text
pyserial==3.5
pyyaml==6.0.2
influxdb-client==1.50.0
paho-mqtt==2.1.0
```

### Recomendación para PyYAML en Raspberry Pi:
- En Raspberry Pi OS (Debian), se recomienda instalar `python3-yaml` mediante el gestor del sistema (`sudo apt install -y python3-yaml`) para disponer del paquete precompilado por la distribución y evitar compilar extensiones en la placa.
- En `edge/requirements.txt` se mantiene fijada la versión probada `pyyaml==6.0.2` para entornos virtuales o desarrollo local.

### Compatibilidad con Raspberry Pi 2 (ARMv7 / 32 bits / `armhf` / sin Docker):
- **100% Pure Python (`py3-none-any.whl`)**: `paho-mqtt`, `pyserial` e `influxdb-client` (junto con `reactivex`, `certifi`, `urllib3`, `python-dateutil`) son paquetes universales en Python puro. **No requieren extensiones nativas en C ni compiladores (`gcc`) en el dispositivo**.
- Se garantiza la instalación inmediata y ligera en Raspberry Pi 2 Modelo B sin sobrecargar la memoria RAM ni requerir Docker.

---

## 2. Arquitectura del Bridge Bidireccional (`bridge.py`)

El bridge actúa como puente concurrente desacoplado:

```text
               +---------------------------------------+
               |         Broker Mosquitto MQTT         |
               +-------------------+-------------------+
                                   |
         tanques/cmd (QoS 1)       |      tanques/ack (QoS 1)
         [id, cmd, target, ts]     |      [ack, ok, reason]
                 |                 |              ^
                 v                 |              |
         +-------------------------+--------------+----+
         |                 edge/bridge.py              |
         |  - Validación de timestamp (ts > 5s -> exp) |
         |  - Deduplicación idempotente por id         |
         |  - Timeout asíncrono de 2.5s -> dev_timeout |
         |  - Cola secuencial de comandos (Queue)      |
         +-----------+--------------------+------------+
                     |                    |
        Línea JSON   |                    | Línea JSON
     (Comando set)   v                    | (Ack / Telemetría)
         +-----------+--------------------+------------+
         |     Dispositivo (Serial / Simulator stdin)  |
         |   - Único hilo lector dueño del puerto      |
         |   - DTR=False, RTS=False (no reset)         |
         +---------------------------------------------+
```

### 2.1 Reglas de Seguridad y Validación de Comandos
1. **Timestamping y Expiración (`ts`)**:
   Todo comando en `tanques/cmd` puede incluir la marca de tiempo `ts` (epoch en milisegundos). Si el comando tiene más de **5000 ms** de antigüedad al momento de ser procesado por el bridge (configurable mediante `COMMAND_MAX_AGE_MS`), **no se envía al hardware** y se emite inmediatamente en `tanques/ack`:
   ```json
   {"ack": "<id>", "ok": false, "reason": "expired"}
   ```
   Si `COMMAND_MAX_AGE_MS=0`, la verificación de expiración se desactiva por completo.
2. **Deduplicación Idempotente en Ventana Deslizante**:
   El bridge mantiene una ventana deslizante de los últimos $N=100$ identificadores de comando (`id`) y almacena los acks resueltos.
   - Si ingresa un comando repetido cuyo ack ya fue generado, el bridge **republica el ack original guardado** (con `ok: true` o el resultado que haya tenido).
   - Si el comando aún se encuentra pendiente de respuesta en el puerto serial, el duplicado se **ignora en silencio**.
   - **Bajo ninguna circunstancia se emite un ack de fallo con `reason: "duplicate"`**.
3. **Correlación Asíncrona y Timeout de Dispositivo (2.5 s)**:
   Al despachar un comando al microcontrolador, se inicia un temporizador de **2.5 segundos**. Si el hardware no responde dentro de esa ventana, el comando se desasocia y se publica:
   ```json
   {"ack": "<id>", "ok": false, "reason": "device_timeout"}
   ```
4. **Propiedades MQTT**:
   - `clean_session = True` en la conexión del bridge para evitar recibir ráfagas retenidas obsoletas tras caídas.
   - Sin flag `retain` en la emisión de acks ni comandos.
   - Suscripción garantizada a `tanques/cmd` con **QoS 1** en el callback `on_connect` (y en cada reconexión automática).

---

## 3. Reloj en Raspberry Pi 2 (sin RTC), Sincronización NTP e InfluxDB

La Raspberry Pi 2 carece de chip de reloj en tiempo real con batería (RTC). Si la placa arranca sin conexión a internet, su reloj del sistema se inicializa en una fecha histórica (año 1970 o la fecha de compilación del kernel).

### 3.1 Sellado de Tiempo en InfluxDB
Para desacoplar la precisión temporal del estado del reloj en la Raspberry Pi:
- El bridge formatea la telemetría en InfluxDB Line Protocol **sin timestamp explícito por defecto** (`telemetry,mode=auto ...`).
- InfluxDB asigna automáticamente la hora oficial del servidor en el momento exacto de la recepción HTTP.
- Para pruebas donde se requiera el reloj local, se dispone de la bandera `--use-local-timestamp`.

### 3.2 Detección de Desfase y Configuración de Expiración
- Al iniciar, el bridge verifica si el año del sistema es inferior a 2025. De ser así, emite una advertencia destacada en los logs solicitando verificar la sincronización horaria o desactivar el control de expiración (`COMMAND_MAX_AGE_MS=0`).
- Si la Pi opera en una red aislada sin internet:
  ```bash
  export COMMAND_MAX_AGE_MS=0
  ```

### 3.3 Sincronización NTP Recomendada
En Raspberry Pi OS, verificar y habilitar la sincronización de red con `systemd-timesyncd`:
```bash
# Comprobar estado de sincronización horaria
timedatectl status

# Habilitar sincronización NTP si está inactiva
sudo timedatectl set-ntp true
sudo systemctl restart systemd-timesyncd
```
En redes locales aisladas con servidor NTP propio en el router, editar `/etc/systemd/timesyncd.conf` y definir:
```ini
[Time]
NTP=192.168.1.1
```

### 3.4 Evaluación de MQTT v5 Message Expiry Interval
Se verificó experimentalmente contra la versión homologada **Mosquitto 2.0.22**:
- Mosquitto soporta de forma nativa la propiedad `MessageExpiryInterval` de MQTT v5.
- Cuando un mensaje se publica con `MessageExpiryInterval = 10` y no hay suscriptores conectados o el consumidor tarda en procesarlo, Mosquitto descuenta el tiempo transcurrido y descarta el paquete automáticamente al expirar, previniendo la acumulación de comandos obsoletos en la cola del broker.

---

## 4. Manejo Serial y Particularidad del Arduino Uno

- **Desactivación de DTR y RTS**: Antes de abrir el descriptor de archivo del puerto serial (`ser.open()`), `pyserial` configura explícitamente `dtr = False` y `rts = False`.
- **Comportamiento del Arduino Uno**:
  > **AVISO IMPORTANTE**: El circuito de hardware del Arduino Uno R3 posee un capacitor conectado a la línea DTR que fuerza un reinicio (*auto-reset*) al abrirse la conexión serial USB, demorando entre **1 y 2 segundos** en ejecutar el bootloader antes de iniciar el loop principal. Durante ese arranque suele enviar texto por el puerto.
  > El bridge está diseñado para **ignorar de forma transparente cualquier línea que no sea un JSON válido**, por lo que el ruido de arranque no afecta la estabilidad ni genera excepciones.
- **Dueño del puerto**: Existe un **único hilo lector** que monopoliza la lectura del puerto. Los comandos entrantes se encolan y se escriben secuencialmente a través de un hilo escritor dedicado.
- **Reconexión con Backoff**: Ante desconexión del cable USB o apagado del microcontrolador, el bridge reintenta la apertura de forma exponencial ($1s, 2s, 4s, \dots, 30s$) sin crashear.

---

## 5. Guía de Instalación en Raspberry Pi 2 (Sin Docker)

En la Raspberry Pi 2 (nodo de borde conectado físicamente al Arduino Uno mediante USB), el bridge se ejecuta nativamente bajo Python 3 con un entorno virtual y se administra como servicio `systemd`.

> **Aviso sobre el usuario y rutas en Raspberry Pi OS**:
> En instalaciones modernas de Raspberry Pi OS, el instalador no crea obligatoriamente el usuario `pi` sino que solicita definir uno personalizado (por ejemplo, `alumno`, `tanques`, etc.).
> Si el usuario configurado en la placa es distinto de `pi`, reemplazá las rutas `/home/pi/...` por `/home/<tu_usuario>/...` tanto al clonar el repositorio como en los campos `User`, `Group` y `WorkingDirectory`/`ExecStart`/`EnvironmentFile` de la unidad systemd (`/etc/systemd/system/tanques-bridge.service`).

### Paso 1: Instalar Paquetes del Sistema
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-yaml git
```

### Paso 2: Clonar el Repositorio y Crear Entorno Virtual
```bash
cd /home/pi  # o /home/<tu_usuario>
git clone <URL_REPOSITORIO> becabelgrano
cd becabelgrano/edge

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Paso 3: Identificar el Puerto Serial del Microcontrolador
Para evitar que el nombre del dispositivo cambie entre reinicios (`/dev/ttyACM0` vs `/dev/ttyACM1`), identificar el enlace por ID persistente:
```bash
ls -l /dev/serial/by-id/
# Ejemplo: /dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_...
```

### Paso 4: Configurar Variables de Entorno y Permisos
Crear el archivo `/home/pi/becabelgrano/edge/.env` con permisos restringidos (`chmod 600`):
```bash
cat << 'EOF' > /home/pi/becabelgrano/edge/.env
INFLUX_URL=http://<IP_SERVIDOR_DOCKER>:8086
INFLUX_TOKEN=<TU_TOKEN_INFLUX>
INFLUX_ORG=utn-frsf
INFLUX_BUCKET=tanques
MQTT_HOST=<IP_SERVIDOR_DOCKER>
MQTT_PORT=1883
MQTT_USER=tanques
MQTT_PASSWORD=<TU_PASSWORD_REAL>
COMMAND_MAX_AGE_MS=5000
EOF

chmod 600 /home/pi/becabelgrano/edge/.env
```

### Paso 5: Instalar y Activar el Servicio Systemd
El archivo de servicio asigna el usuario sin privilegios `pi` e incorpora el grupo `dialout` para acceso a dispositivos seriales:
```bash
sudo cp /home/pi/becabelgrano/edge/systemd/tanques-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tanques-bridge
sudo systemctl start tanques-bridge
```

### Paso 6: Inspeccionar Logs del Servicio
```bash
sudo journalctl -u tanques-bridge -f
```

---

## 6. Pruebas Locales y Herramientas de Diagnóstico

### 6.1 Con Simulador Interno (Desarrollo)
Cargar variables de entorno previas y ejecutar sin incluir contraseñas en la línea de comandos:
```bash
# Exportar credenciales del entorno
export MQTT_USER=tanques
export MQTT_PASSWORD=<clave_real>

# Iniciar bridge consumiendo datos del simulador interno
python edge/bridge.py --source sim --sim-speed 2.0
```

### 6.2 Herramienta de Envío de Comandos (`edge/tools/send_cmd.py`)
Permite publicar comandos estructurados en `tanques/cmd` para verificar la respuesta del Bridge y del hardware:
```bash
# Encender bomba con timestamp fresco (0 s de edad)
python edge/tools/send_cmd.py cmd-001 true

# Apagar bomba con comando de 10 segundos de antigüedad (debe descartarse por 'expired')
python edge/tools/send_cmd.py cmd-viejo false 10

# Simular comando con broker y credenciales específicas si difieren de las variables de entorno
python edge/tools/send_cmd.py cmd-002 true --host localhost --port 1883
```

### 6.3 Con Microcontrolador Físico
```bash
# En Windows:
python edge/bridge.py --source serial:COM5:115200

# En Linux:
python edge/bridge.py --source serial:/dev/ttyACM0:115200
```

### 6.4 Suite Completa de Tests Automatizados
Ejecuta de forma conjunta todas las pruebas unitarias y de integración del módulo edge (20 tests en total):
```bash
python -m pytest edge/ -v
```
Verifica:
- 10 tests de física del simulador, interlocks, retries y formateo InfluxDB (`edge/test_edge.py`).
- 10 tests del Bridge bidireccional, acks, interlocks, timeouts, expiraciones, deduplicación idempotente, arranque con broker caído y flujo E2E con el simulador (`edge/tests/test_bridge.py`).
