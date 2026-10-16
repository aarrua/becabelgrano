# Edge Computing: Simulador Físico y Bridge Bidireccional Serial/MQTT (UTN FRSF / GITDA)

Este directorio contiene los componentes que corren en el nodo de borde (*Edge Node* en Raspberry Pi) encargados de:
1. La ingesta continua de telemetría física o simulada hacia InfluxDB 2.x con sellado de tiempo UTC oficial.
2. El canal bidireccional de control entre el Backend (vía Mosquitto MQTT) y el microcontrolador (vía Serial USB o stdin del simulador).
3. La simulación de dinámica física e hidráulica de los tanques interconectados para experimentación en desarrollo.

---

## 1. Dependencias Fijadas y Compatibilidad ARM 32-bit (Raspberry Pi 2)

Las dependencias en `edge/requirements.txt` están fijadas a versiones exactas verificadas:

```text
pyserial==3.5
pyyaml==6.0.2
influxdb-client==1.50.0
paho-mqtt==2.1.0
```

### Compatibilidad con Raspberry Pi 2 (ARMv7 / 32 bits / `armhf` / sin Docker):
- **100% Pure Python (`py3-none-any.whl`)**: `paho-mqtt`, `pyserial` e `influxdb-client` (junto con sus dependencias directas `reactivex`, `certifi`, `urllib3`, `python-dateutil`) son paquetes universales en Python puro. **No requieren extensiones nativas en C ni invocación a `gcc` / compiladores**.
- **PyYAML**: En Raspberry Pi OS (Debian), se puede instalar mediante el gestor del sistema (`sudo apt install python3-yaml`) o a través de piwheels precompilado.
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
         |  - Deduplicación por id en ventana de N     |
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
   Todo comando en `tanques/cmd` incluye la marca de tiempo `ts` (epoch en milisegundos). Si el comando tiene más de **5 segundos de antigüedad** al momento de ser procesado por el bridge (por ejemplo, por encolamiento previo en el broker o retrasos en la red), **no se envía al hardware** y se emite inmediatamente en `tanques/ack`:
   ```json
   {"ack": "<id>", "ok": false, "reason": "expired"}
   ```
2. **Deduplicación en Ventana Deslizante**:
   El bridge mantiene una ventana deslizante de los últimos $N=100$ identificadores de comando (`id`). Si ingresa un comando repetido, se rechaza sin accionar el actuador:
   ```json
   {"ack": "<id>", "ok": false, "reason": "duplicate"}
   ```
3. **Correlación Asíncrona y Timeout de Dispositivo (2.5 s)**:
   Al despachar un comando válido al microcontrolador, se inicia un temporizador de **2.5 segundos**. Si el hardware no responde dentro de esa ventana, el comando se desasocia y se publica:
   ```json
   {"ack": "<id>", "ok": false, "reason": "device_timeout"}
   ```
4. **Propiedades MQTT**:
   - `clean_session = True` en la conexión del bridge para evitar recibir ráfagas retenidas obsoletas tras caídas.
   - Sin flag `retain` en la emisión de acks ni comandos.
   - Suscripción garantizada a `tanques/cmd` con **QoS 1** en el callback `on_connect` (y en cada reconexión automática).

---

## 3. Manejo Serial y Particularidad del Arduino Uno

- **Desactivación de DTR y RTS**: Antes de abrir el descriptor de archivo del puerto serial (`ser.open()`), `pyserial` configura explícitamente `dtr = False` y `rts = False`.
- **Comportamiento del Arduino Uno**:
  > **AVISO IMPORTANTE**: El circuito de hardware del Arduino Uno R3 posee un capacitor conectado a la línea DTR que fuerza un reinicio (*auto-reset*) al abrirse la conexión serial USB, demorando entre **1 y 2 segundos** en ejecutar el bootloader antes de iniciar el loop principal. Durante ese arranque suele enviar texto por el puerto.
  > El bridge está diseñado para **ignorar de forma transparente cualquier línea que no sea un JSON válido**, por lo que el ruido de arranque no afecta la estabilidad ni genera excepciones.
- **Dueño del puerto**: Existe un **único hilo lector** que monopoliza la lectura del puerto. Los comandos entrantes se encolan y se escriben secuencialmente a través de un hilo escritor dedicado.
- **Reconexión con Backoff**: Ante desconexión del cable USB o apagado del microcontrolador, el bridge reintenta la apertura de forma exponencial ($1s, 2s, 4s, \dots, 30s$) sin crashear.

---

## 4. Guía de Instalación en Raspberry Pi 2 (Sin Docker)

En la Raspberry Pi 2 (nodo de borde conectado físicamente al Arduino / ESP32 mediante USB), el bridge se ejecuta nativamente bajo Python 3 con un entorno virtual y se administra como servicio `systemd`.

### Paso 1: Instalar Paquetes del Sistema
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

### Paso 2: Clonar el Repositorio y Crear Entorno Virtual
```bash
cd /home/pi
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

### Paso 4: Configurar Variables de Entorno
Crear el archivo `/home/pi/becabelgrano/edge/.env`:
```env
INFLUX_URL=http://<IP_SERVIDOR_DOCKER>:8086
INFLUX_TOKEN=tanques-super-secret-token-2025
INFLUX_ORG=utn-frsf
INFLUX_BUCKET=tanques
MQTT_HOST=<IP_SERVIDOR_DOCKER>
MQTT_PORT=1883
MQTT_USER=tanques
MQTT_PASSWORD=<TU_PASSWORD_REAL>
```

### Paso 5: Instalar y Activar el Servicio Systemd
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

## 5. Pruebas Locales del Bridge

### 5.1 Con Simulador Interno (Desarrollo)
```bash
# Iniciar bridge consumiendo datos del simulador interno
python edge/bridge.py --source sim --sim-speed 2.0 --mqtt-host localhost --mqtt-user tanques --mqtt-password <tu_clave>
```

### 5.2 Con Microcontrolador Físico
```bash
# En Windows:
python edge/bridge.py --source serial:COM5:115200

# En Linux:
python edge/bridge.py --source serial:/dev/ttyACM0:115200
```

### 5.3 Suite de Tests Automatizados
```bash
python -m pytest edge/tests/test_bridge.py -v
```
Verifica unitariamente comandos válidos, acks, interlocks, timeouts, expiraciones, duplicados, descarte de ruido no JSON, persistencia de telemetría e integración de punta a punta con el simulador.
