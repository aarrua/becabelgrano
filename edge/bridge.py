#!/usr/bin/env python3
"""
Bridge de Telemetría y Control Bidireccional: Serial/Simulador <-> MQTT / InfluxDB 2.x
====================================================================================
Universidad Tecnológica Nacional - Facultad Regional Santa Fe (UTN FRSF / GITDA)
Requiere Python 3.9+ (Sintaxis compatible con Raspberry Pi OS y 32-bit ARM).

Funciones del Bridge:
1. Ingesta de Telemetría:
   Lee tramas JSON desde el puerto serial del microcontrolador (o simulador de tanques).
   Por defecto omite el timestamp explícito en Line Protocol para que InfluxDB 2.x
   asigne la hora oficial de recepción en el servidor (crucial para Raspberry Pi 2 sin RTC).
2. Canal Bidireccional de Comandos (MQTT <-> Serial):
   - Se suscribe al tópico 'tanques/cmd' (QoS 1) en broker Mosquitto.
   - Seguridad y validación: rechaza comandos expirados (> COMMAND_MAX_AGE_MS, configurable;
     0 desactiva) y deduplica por 'id' en una ventana deslizante de N elementos.
   - Ante duplicados: republica el ack original guardado o lo ignora en silencio sin emitir
     ack de fallo con el mismo id.
   - Despacha los comandos válidos hacia el puerto serial (o stdin del simulador) mediante
     una cola secuencial, manteniendo un único hilo lector dueño del puerto.
   - Correlación asíncrona por 'id': si el equipo físico responde en < 2.5 s, publica el
     resultado en 'tanques/ack' (QoS 1). Si vence el timeout, emite 'device_timeout'.
3. Resiliencia en el Borde:
   - Desactiva DTR y RTS antes de abrir el puerto serial para evitar el reinicio del Arduino Uno (RESET por DTR).
   - Reconexión automática con backoff exponencial ante caídas del puerto serie y del broker MQTT.
   - Detección y aviso en el arranque si el reloj del sistema se encuentra desfasado.
   - Ignora líneas no JSON o ruido de arranque sin crashear.
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterator, List, Optional, Set, Tuple, Union

try:
    import paho.mqtt.client as mqtt  # type: ignore
except ImportError:
    mqtt = None

try:
    import serial  # type: ignore
except ImportError:
    serial = None

# Rutas resueltas relativas a la ubicación del script
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SIM_PATH = BASE_DIR / "simulator.py"
DEFAULT_CONFIG_PATH = BASE_DIR / "config.yaml"

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("edge-bridge")


# ==============================================================================
# InfluxDB 2.x Line Protocol & Client
# ==============================================================================

class InfluxWriter:
    """Cliente HTTP liviano para InfluxDB 2.x compatible con Line Protocol."""

    def __init__(self, url: str, token: str, org: str, bucket: str, timeout: float = 3.0) -> None:
        if not token or not str(token).strip():
            raise ValueError("Token de autenticación InfluxDB 2.x no configurado o vacío.")
        self.url = url.rstrip("/")
        self.token = token.strip()
        self.org = org
        self.bucket = bucket
        self.timeout = timeout
        query_params = urllib.parse.urlencode({"org": self.org, "bucket": self.bucket, "precision": "ns"})
        self.endpoint = f"{self.url}/api/v2/write?{query_params}"

    def write_line_protocol(self, line: str) -> bool:
        """Envía una o más líneas de Line Protocol a InfluxDB 2.x."""
        req = urllib.request.Request(
            url=self.endpoint,
            data=line.encode("utf-8"),
            headers={
                "Authorization": f"Token {self.token}",
                "Content-Type": "text/plain; charset=utf-8",
                "User-Agent": "utn-frsf-edge-bridge/1.0"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.status in (200, 204)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            logger.error("HTTP %s escribiendo en InfluxDB: %s", e.code, error_body)
            return False
        except urllib.error.URLError as e:
            logger.warning("No se pudo conectar a InfluxDB (%s): %s", self.url, e.reason)
            return False
        except Exception as e:
            logger.error("Excepción inesperada al escribir en InfluxDB: %s", e)
            return False


def format_influx_line(data: Dict[str, Any], timestamp_ns: Optional[int] = None) -> Optional[str]:
    """
    Convierte una trama JSON de telemetría al Line Protocol de InfluxDB.
    Si timestamp_ns es None, omite el timestamp para que InfluxDB asigne la hora de recepción
    (estrategia por defecto recomendada para Raspberry Pi 2 sin RTC).
    """
    if data.get("v") != 1:
        logger.debug("Trama descartada por versión de contrato incompatible: %s", data.get("v"))
        return None

    try:
        mode = str(data.get("mode", "auto"))
        seq = int(data["seq"])
        uptime_ms = int(data["uptime_ms"])

        tank_a = data["tank_a"]
        tank_b = data["tank_b"]
        actuators = data.get("actuators", {})
        alarms = data.get("alarms", {})

        fields = [
            f"seq={seq}i",
            f"uptime_ms={uptime_ms}i",
        ]

        if tank_a.get("weight_g") is not None:
            fields.append(f"tank_a_weight_g={float(tank_a['weight_g']):.2f}")
        if tank_a.get("level_pct") is not None:
            fields.append(f"tank_a_level_pct={float(tank_a['level_pct']):.2f}")
        if tank_a.get("temp_c") is not None:
            fields.append(f"tank_a_temp_c={float(tank_a['temp_c']):.2f}")

        if tank_b.get("weight_g") is not None:
            fields.append(f"tank_b_weight_g={float(tank_b['weight_g']):.2f}")
        if tank_b.get("level_pct") is not None:
            fields.append(f"tank_b_level_pct={float(tank_b['level_pct']):.2f}")
        if tank_b.get("temp_c") is not None:
            fields.append(f"tank_b_temp_c={float(tank_b['temp_c']):.2f}")

        if data.get("flow_lpm") is not None:
            fields.append(f"flow_lpm={float(data['flow_lpm']):.2f}")

        fields.append(f"pump={'true' if actuators.get('pump', False) else 'false'}")
        fields.append(f"overflow_a={'true' if alarms.get('overflow_a', False) else 'false'}")
        fields.append(f"overflow_b={'true' if alarms.get('overflow_b', False) else 'false'}")
        fields.append(f"sensor_fault={'true' if alarms.get('sensor_fault', False) else 'false'}")

        if timestamp_ns is not None:
            line = f"telemetry,mode={mode} {','.join(fields)} {timestamp_ns}"
        else:
            line = f"telemetry,mode={mode} {','.join(fields)}"
        return line
    except (KeyError, TypeError, ValueError) as err:
        logger.warning("Estructura de trama inválida o campo faltante: %s (%s)", err, data)
        return None


# ==============================================================================
# Controlador Principal del Bridge (TanquesBridge)
# ==============================================================================

class TanquesBridge:
    """
    Controlador central del Bridge bidireccional.
    Gestiona la conexión MQTT, la cola secuencial de salida y la correlación de acks.
    """

    def __init__(
        self,
        influx_writer: Optional[InfluxWriter] = None,
        mqtt_host: str = "localhost",
        mqtt_port: int = 1883,
        mqtt_user: Optional[str] = None,
        mqtt_password: Optional[str] = None,
        cmd_topic: str = "tanques/cmd",
        ack_topic: str = "tanques/ack",
        cmd_timeout_s: float = 2.5,
        command_max_age_ms: int = 5000,
        max_cmd_age_s: Optional[float] = None,
        dedup_window_size: int = 100,
        log_interval: int = 30,
        use_server_timestamp: bool = True,
        mqtt_client: Optional[Any] = None,
    ) -> None:
        if max_cmd_age_s is not None:
            command_max_age_ms = int(max_cmd_age_s * 1000)

        self.influx_writer = influx_writer
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_password = mqtt_password
        self.cmd_topic = cmd_topic
        self.ack_topic = ack_topic
        self.cmd_timeout_s = cmd_timeout_s
        self.command_max_age_ms = command_max_age_ms
        self.log_interval = log_interval
        self.use_server_timestamp = use_server_timestamp

        # Deduplicación de comandos en ventana deslizante y memoria de acks
        self.dedup_window_size = dedup_window_size
        self._dedup_deque: Deque[str] = collections.deque(maxlen=dedup_window_size)
        self._dedup_set: Set[str] = set()
        self._recent_acks: Dict[str, Dict[str, Any]] = {}

        # Comandos pendientes de ack: {cmd_id: {"timer": Timer, "created_at": float}}
        self._pending_commands: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

        # Cola de comandos hacia el hardware/simulador
        self.command_queue: queue.Queue[str] = queue.Queue()

        # Métricas y estado
        self.telemetry_success_count = 0
        self.running = True

        # Advertencia de reloj desfasado en arranque
        self._check_system_clock()

        # Inicialización de cliente MQTT
        self.mqtt_client = mqtt_client
        if self.mqtt_client is None and mqtt is not None:
            self._init_mqtt_client()

    def _check_system_clock(self) -> None:
        """Verifica si el reloj del sistema aparenta estar desfasado (típico en Pi 2 sin RTC)."""
        current_year = datetime.now(timezone.utc).year
        if current_year < 2025:
            logger.warning(
                "ATENCIÓN: El reloj del sistema parece desfasado (año %d < 2025). "
                "La Raspberry Pi 2 carece de RTC de hardware. Asegúrese de sincronizar NTP (systemd-timesyncd) "
                "o configure COMMAND_MAX_AGE_MS=0 para evitar que los comandos expiren erróneamente.",
                current_year
            )

    def _init_mqtt_client(self) -> None:
        """Configura el cliente paho-mqtt con CallbackAPIVersion.VERSION2 y clean_session=True."""
        client_id = f"tanques-bridge-{os.getpid()}"
        self.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            clean_session=True
        )

        if self.mqtt_user and self.mqtt_password:
            self.mqtt_client.username_pw_set(self.mqtt_user, self.mqtt_password)

        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
        self.mqtt_client.on_message = self._on_mqtt_message

    def start_mqtt(self) -> None:
        """Inicia el cliente MQTT de forma tolerante a caídas iniciales con bucle asíncrono."""
        if not self.mqtt_client:
            logger.warning("Cliente MQTT no inicializado o paho-mqtt no disponible.")
            return

        logger.info("Iniciando conexión MQTT asíncrona a %s:%d...", self.mqtt_host, self.mqtt_port)
        try:
            self.mqtt_client.connect_async(self.mqtt_host, self.mqtt_port, keepalive=60)
            self.mqtt_client.loop_start()
        except Exception as e:
            logger.warning("Aviso al iniciar cliente MQTT: %s. Reintentos automáticos habilitados.", e)

    def stop(self) -> None:
        """Detiene el bridge y libera recursos."""
        self.running = False
        with self._lock:
            for item in self._pending_commands.values():
                timer = item.get("timer")
                if timer:
                    timer.cancel()
            self._pending_commands.clear()

        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # Callbacks MQTT
    # --------------------------------------------------------------------------

    def _on_mqtt_connect(self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
        """Callback invocado al conectar o reconectar al broker MQTT."""
        if reason_code == 0:
            logger.info("✓ Conectado exitosamente a Mosquitto (%s:%d). Suscribiendo a '%s' (QoS 1)...",
                        self.mqtt_host, self.mqtt_port, self.cmd_topic)
            client.subscribe(self.cmd_topic, qos=1)
        else:
            logger.warning("Falla al conectar con broker MQTT: %s", reason_code)

    def _on_mqtt_disconnect(self, client: Any, userdata: Any, disconnect_flags: Any, reason_code: Any, properties: Any = None) -> None:
        """Callback invocado ante desconexión del broker MQTT."""
        logger.warning("Desconexión de Mosquitto (%s). El cliente intentará reconectar automáticamente.", reason_code)

    def _on_mqtt_message(self, client: Any, userdata: Any, message: Any) -> None:
        """Procesa mensajes que ingresan al tópico de comandos (tanques/cmd)."""
        payload_str = message.payload.decode("utf-8", errors="replace").strip()
        logger.debug("Mensaje MQTT recibido en %s: %s", message.topic, payload_str)
        self.handle_incoming_command(payload_str)

    # --------------------------------------------------------------------------
    # Gestión de Comandos y Seguridad
    # --------------------------------------------------------------------------

    def handle_incoming_command(self, payload_str: str) -> None:
        """
        Valida el comando entrante:
        - Sintaxis JSON.
        - Expiración de timestamp (ts) si command_max_age_ms > 0.
        - Deduplicación por 'id': si ya se procesó, republica el ack original o ignora en silencio.
        - Si es nuevo y válido, lo encola para envío serial y programa el timeout de 2.5 s.
        """
        try:
            cmd = json.loads(payload_str)
        except json.JSONDecodeError:
            logger.warning("Comando descartado: formato no es un JSON válido: %s", payload_str)
            return

        cmd_id = str(cmd.get("id", ""))
        if not cmd_id:
            logger.warning("Comando descartado por carecer de campo 'id': %s", payload_str)
            return

        # 1. Validación de Expiración por Timestamp (ts) si está habilitada (> 0)
        if self.command_max_age_ms > 0:
            now_epoch_ms = int(time.time() * 1000)
            cmd_ts = cmd.get("ts")
            if isinstance(cmd_ts, (int, float)):
                age_ms = now_epoch_ms - cmd_ts
                if age_ms > self.command_max_age_ms:
                    logger.warning("Comando id='%s' EXPIRADO (antigüedad: %.2f s > %.2f s). No se envía al hardware.",
                                   cmd_id, age_ms / 1000.0, self.command_max_age_ms / 1000.0)
                    self.publish_ack({"ack": cmd_id, "ok": False, "reason": "expired"})
                    return

        # 2. Deduplicación por 'id'
        with self._lock:
            # Caso 2A: Si ya tenemos el ack original guardado para este id, republicarlo
            if cmd_id in self._recent_acks:
                logger.info("Comando id='%s' ya resuelto anteriormente. Republicando ack original guardado.", cmd_id)
                self.publish_ack(self._recent_acks[cmd_id])
                return

            # Caso 2B: Si aún se encuentra pendiente de respuesta física en serial
            if cmd_id in self._pending_commands:
                logger.info("Comando id='%s' ya está pendiente de respuesta física. Ignorando reintento en silencio.", cmd_id)
                return

            # Caso 2C: Si fue visto en la ventana pero no tiene ack guardado
            if cmd_id in self._dedup_set:
                logger.info("Comando id='%s' duplicado ya procesado. Ignorando en silencio.", cmd_id)
                return

            # Registrar en la ventana deslizante
            if len(self._dedup_deque) >= self.dedup_window_size:
                oldest_id = self._dedup_deque.popleft()
                self._dedup_set.discard(oldest_id)
                self._recent_acks.pop(oldest_id, None)

            self._dedup_deque.append(cmd_id)
            self._dedup_set.add(cmd_id)

            # 3. Registrar comando pendiente y programar timer de timeout
            timer = threading.Timer(self.cmd_timeout_s, self._handle_command_timeout, args=(cmd_id,))
            timer.daemon = True
            self._pending_commands[cmd_id] = {
                "timer": timer,
                "created_at": time.time(),
                "raw_cmd": cmd
            }
            timer.start()

        # 4. Encolar comando hacia el hardware
        logger.info("Comando id='%s' validado y encolado hacia el equipo físico: %s", cmd_id, payload_str)
        self.command_queue.put(payload_str)

    def _handle_command_timeout(self, cmd_id: str) -> None:
        """Callback ejecutado si el microcontrolador no responde en tiempo límite."""
        with self._lock:
            if cmd_id not in self._pending_commands:
                return
            del self._pending_commands[cmd_id]

        logger.error("TIMEOUT: El equipo no respondió al comando id='%s' en %.1f s. Emitiendo 'device_timeout'.",
                     cmd_id, self.cmd_timeout_s)
        timeout_ack = {"ack": cmd_id, "ok": False, "reason": "device_timeout"}
        with self._lock:
            self._recent_acks[cmd_id] = timeout_ack
        self.publish_ack(timeout_ack)

    def publish_ack(self, ack_payload: Dict[str, Any]) -> None:
        """Publica la confirmación o rechazo en 'tanques/ack' con QoS 1 (sin retain)."""
        if not self.mqtt_client:
            logger.debug("No se puede publicar ack sin cliente MQTT: %s", ack_payload)
            return

        payload_bytes = json.dumps(ack_payload).encode("utf-8")
        try:
            self.mqtt_client.publish(self.ack_topic, payload_bytes, qos=1, retain=False)
            logger.info("Ack publicado en %s (QoS 1): %s", self.ack_topic, ack_payload)
        except Exception as e:
            logger.error("Error al publicar ack en Mosquitto: %s", e)

    # --------------------------------------------------------------------------
    # Procesamiento de Líneas Entrantes desde el Dispositivo (Serial / Simulador)
    # --------------------------------------------------------------------------

    def process_device_line(self, raw_line: str) -> None:
        """
        Procesa una línea recibida desde el microcontrolador o simulador:
        - Si no es JSON: se ignora sin crashear.
        - Si contiene el campo 'ack': resuelve el comando pendiente, guarda el ack y publica en MQTT.
        - Si es telemetría: formatea a Line Protocol y persiste en InfluxDB.
        """
        line = raw_line.strip()
        if not line:
            return

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Línea ignorada (no es JSON): %s", line)
            return

        if not isinstance(data, dict):
            logger.debug("Línea JSON descartada (no es objeto dict): %s", line)
            return

        # Caso A: Respuesta ACK de un comando
        if "ack" in data:
            ack_id = str(data["ack"])
            with self._lock:
                pending = self._pending_commands.pop(ack_id, None)
                if pending:
                    timer = pending.get("timer")
                    if timer:
                        timer.cancel()
                    elapsed = time.time() - pending.get("created_at", time.time())
                    logger.info("✓ ACK recibido del equipo para id='%s' (tiempo: %.3f s): ok=%s",
                                ack_id, elapsed, data.get("ok"))
                else:
                    logger.warning("ACK recibido para comando id='%s' no pendiente o ya expirado.", ack_id)

                # Guardar en memoria de acks recientes para republicar si ingresa un duplicado
                self._recent_acks[ack_id] = data

            self.publish_ack(data)
            return

        # Caso B: Trama periódica de Telemetría
        if not self.influx_writer:
            return

        timestamp_ns = None if self.use_server_timestamp else time.time_ns()
        influx_line = format_influx_line(data, timestamp_ns)
        if not influx_line:
            return

        success = self.influx_writer.write_line_protocol(influx_line)
        if success:
            self.telemetry_success_count += 1
            if self.log_interval > 0 and self.telemetry_success_count % self.log_interval == 0:
                iso_time = datetime.now(timezone.utc).isoformat()
                logger.info(
                    "[%s] InfluxDB: %d escrituras exitosas acumuladas (última seq=%d | A: %s%% | B: %s%% | Bomba: %s | Q: %.2f L/min)",
                    iso_time,
                    self.telemetry_success_count,
                    data.get("seq", 0),
                    data.get("tank_a", {}).get("level_pct"),
                    data.get("tank_b", {}).get("level_pct"),
                    data.get("actuators", {}).get("pump"),
                    data.get("flow_lpm", 0.0)
                )


# ==============================================================================
# Hilos y Pipelines de Comunicación con el Hardware
# ==============================================================================

def stream_stdin() -> Iterator[str]:
    """Generador que lee líneas desde standard input."""
    for line in sys.stdin:
        yield line


def stream_simulator(
    sim_script: Optional[Union[Path, str]] = None,
    config_path: Optional[Union[Path, str]] = None,
    extra_args: Optional[List[str]] = None,
    initial_backoff: float = 1.0,
    max_backoff: float = 30.0,
    pump_on: bool = False,
) -> Iterator[str]:
    """
    Ejecuta el simulador en un subproceso y streamea su stdout.
    Mantiene compatibilidad con la suite de tests de Fase 1.
    """
    script_path = Path(sim_script) if sim_script else DEFAULT_SIM_PATH
    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    cmd = [sys.executable, str(script_path)]
    if cfg_path and (not extra_args or "--config" not in extra_args):
        cmd.extend(["--config", str(cfg_path)])
    if pump_on and (not extra_args or "--pump-on" not in extra_args):
        cmd.append("--pump-on")
    if extra_args:
        cmd.extend(extra_args)

    backoff = initial_backoff

    while True:
        proc: Optional[subprocess.Popen[str]] = None
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                backoff = initial_backoff
                yield line

            ret_code = proc.wait(timeout=2)
            stderr_out = proc.stderr.read() if proc.stderr else ""
            if ret_code != 0:
                logger.error("El simulador finalizó con error %d: %s", ret_code, stderr_out.strip() or "(vacío)")
        except Exception as e:
            logger.error("Error al ejecutar simulador: %s", e)
        finally:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=1)
                except Exception:
                    pass

        time.sleep(backoff)
        backoff = min(backoff * 2.0, max_backoff)


def run_bridge(
    source_spec: str,
    influx: InfluxWriter,
    sim_speed: float = 1.0,
    config_path: Optional[Union[Path, str]] = None,
    log_interval: int = 30,
    pump_on: bool = False,
) -> None:
    """
    Punto de entrada compatible con Fase 1 para ejecutar el bridge de forma procedural.
    """
    resolved_config = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    bridge = TanquesBridge(influx_writer=influx, log_interval=log_interval, use_server_timestamp=False)

    if source_spec == "stdin":
        lines_iterator = stream_stdin()
    elif source_spec.startswith("sim"):
        args = ["--speed", str(sim_speed)]
        if pump_on:
            args.append("--pump-on")
        lines_iterator = stream_simulator(
            sim_script=DEFAULT_SIM_PATH,
            config_path=resolved_config,
            extra_args=args,
            pump_on=pump_on,
        )
    elif source_spec.startswith("serial:"):
        parts = source_spec[len("serial:"):].split(":")
        port = parts[0]
        baud = int(parts[1]) if len(parts) > 1 else 115200
        run_serial_pipeline(bridge, port, baud)
        return
    else:
        logger.error("Fuente desconocida: %s", source_spec)
        return

    for line in lines_iterator:
        bridge.process_device_line(line)


def run_serial_pipeline(bridge: TanquesBridge, port: str, baudrate: int = 115200) -> None:
    """
    Gestiona la comunicación con el microcontrolador serial:
    - Hilo único lector dueño del puerto.
    - Cola de escritura secuencial de comandos.
    - Reconexión continua con backoff exponencial sin crashear si el serial desaparece.
    """
    if serial is None:
        logger.error("pyserial no está disponible. Ejecute: pip install pyserial")
        sys.exit(1)

    backoff = 1.0
    max_backoff = 30.0

    while bridge.running:
        ser: Optional[serial.Serial] = None
        writer_thread: Optional[threading.Thread] = None
        try:
            logger.info("Intentando abrir puerto serial %s a %d baudios (DTR=False, RTS=False)...", port, baudrate)
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = baudrate
            ser.timeout = 1.0
            ser.dtr = False
            ser.rts = False
            ser.open()

            logger.info("✓ Puerto serial %s conectado exitosamente.", port)
            backoff = 1.0

            def _serial_writer() -> None:
                while bridge.running and ser and ser.is_open:
                    try:
                        cmd_line = bridge.command_queue.get(timeout=0.5)
                        data_to_send = (cmd_line.strip() + "\n").encode("utf-8")
                        ser.write(data_to_send)
                        ser.flush()
                        logger.debug("Comando enviado al serial: %s", cmd_line)
                    except queue.Empty:
                        continue
                    except Exception as err:
                        logger.warning("Error escribiendo comando en serial: %s", err)
                        break

            writer_thread = threading.Thread(target=_serial_writer, daemon=True)
            writer_thread.start()

            while bridge.running and ser.is_open:
                line_bytes = ser.readline()
                if not line_bytes:
                    continue
                try:
                    line = line_bytes.decode("utf-8", errors="ignore")
                    bridge.process_device_line(line)
                except Exception as dec_err:
                    logger.debug("Error decodificando línea serial: %s", dec_err)

        except (serial.SerialException, OSError) as e:
            logger.warning("Aviso o desconexión en puerto serial %s: %s", port, e)
        except Exception as e:
            logger.error("Error inesperado en gestión serial: %s", e)
        finally:
            if ser and ser.is_open:
                try:
                    ser.close()
                except Exception:
                    pass
            if writer_thread and writer_thread.is_alive():
                writer_thread.join(timeout=1.0)

        if bridge.running:
            logger.info("Reintentando conexión serial en %.1f segundos...", backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2.0, max_backoff)


def run_simulator_pipeline(
    bridge: TanquesBridge,
    sim_script: Optional[Union[Path, str]] = None,
    config_path: Optional[Union[Path, str]] = None,
    sim_speed: float = 1.0,
    pump_on: bool = False,
) -> None:
    """
    Ejecuta el simulador en un subproceso con comunicación bidireccional por stdin/stdout.
    """
    script_path = Path(sim_script) if sim_script else DEFAULT_SIM_PATH
    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    cmd = [sys.executable, str(script_path), "--config", str(cfg_path), "--speed", str(sim_speed)]
    if pump_on:
        cmd.append("--pump-on")

    backoff = 1.0
    max_backoff = 30.0

    while bridge.running:
        logger.info("Iniciando subproceso del simulador: %s", " ".join(cmd))
        proc: Optional[subprocess.Popen[str]] = None
        writer_thread: Optional[threading.Thread] = None

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            def _sim_writer() -> None:
                while bridge.running and proc and proc.poll() is None:
                    try:
                        cmd_line = bridge.command_queue.get(timeout=0.5)
                        if proc and proc.stdin:
                            proc.stdin.write(cmd_line.strip() + "\n")
                            proc.stdin.flush()
                            logger.debug("Comando enviado al simulador por stdin: %s", cmd_line)
                    except queue.Empty:
                        continue
                    except Exception as err:
                        logger.warning("Error escribiendo en stdin del simulador: %s", err)
                        break

            writer_thread = threading.Thread(target=_sim_writer, daemon=True)
            writer_thread.start()

            assert proc.stdout is not None
            for raw_line in proc.stdout:
                backoff = 1.0
                bridge.process_device_line(raw_line)

            ret_code = proc.wait(timeout=2)
            logger.warning("El subproceso del simulador finalizó con código %s", ret_code)

        except Exception as e:
            logger.error("Error en comunicación con el subproceso del simulador: %s", e)
        finally:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=1)
                except Exception:
                    pass
            if writer_thread and writer_thread.is_alive():
                writer_thread.join(timeout=1.0)

        if bridge.running:
            logger.info("Reintentando lanzar el simulador en %.1f segundos...", backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2.0, max_backoff)


# ==============================================================================
# Punto de Entrada Principal (CLI)
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge Serial/Simulador <-> MQTT / InfluxDB 2.x (UTN FRSF)")
    parser.add_argument("--source", type=str,
                        default=os.environ.get("BRIDGE_SOURCE", "sim"),
                        help="Fuente de datos: 'sim', 'stdin', o 'serial:<puerto>[:baud]' (default: 'sim' o BRIDGE_SOURCE)")
    parser.add_argument("--serial-port", type=str,
                        default=os.environ.get("SERIAL_PORT", ""),
                        help="Puerto serial si no se especifica en --source (ej: COM5 o /dev/ttyUSB0)")
    parser.add_argument("--baudrate", type=int, default=115200,
                        help="Velocidad en baudios para el puerto serial (default: 115200)")
    parser.add_argument("--sim-speed", type=float, default=1.0,
                        help="Multiplicador de velocidad si se usa --source sim")
    parser.add_argument("--pump-on", action="store_true",
                        help="Inicia el simulador con la bomba encendida")
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG_PATH),
                        help="Ruta al archivo config.yaml")
    parser.add_argument("--log-every", type=int, default=30,
                        help="Frecuencia de escrituras exitosas para emitir log INFO")
    parser.add_argument("--verbose", action="store_true",
                        help="Habilita logs detallados a nivel DEBUG")
    parser.add_argument("--command-max-age-ms", type=int,
                        default=int(os.environ.get("COMMAND_MAX_AGE_MS", "5000")),
                        help="Antigüedad máxima admisible en ms para comandos (default: 5000; 0 desactiva)")
    parser.add_argument("--use-local-timestamp", action="store_true",
                        help="Envía el timestamp local del bridge a InfluxDB (por defecto se omite para usar la hora del servidor)")

    # InfluxDB (lee valores por defecto desde variables de entorno)
    parser.add_argument("--influx-url", type=str,
                        default=os.environ.get("INFLUX_URL", "http://localhost:8086"),
                        help="URL base de InfluxDB 2.x (default: $INFLUX_URL o http://localhost:8086)")
    parser.add_argument("--influx-token", type=str,
                        default=os.environ.get("INFLUX_TOKEN"),
                        help="Token de autenticación InfluxDB 2.x (default: $INFLUX_TOKEN)")
    parser.add_argument("--influx-org", type=str,
                        default=os.environ.get("INFLUX_ORG", "utn-frsf"),
                        help="Organización en InfluxDB (default: $INFLUX_ORG)")
    parser.add_argument("--influx-bucket", type=str,
                        default=os.environ.get("INFLUX_BUCKET", "tanques"),
                        help="Bucket de destino en InfluxDB (default: $INFLUX_BUCKET)")

    # Mosquitto MQTT (lee credenciales desde variables de entorno)
    parser.add_argument("--mqtt-host", type=str,
                        default=os.environ.get("MQTT_HOST", "localhost"),
                        help="Host del broker Mosquitto MQTT (default: $MQTT_HOST o localhost)")
    parser.add_argument("--mqtt-port", type=int,
                        default=int(os.environ.get("MQTT_PORT", "1883")),
                        help="Puerto del broker Mosquitto MQTT (default: $MQTT_PORT o 1883)")
    parser.add_argument("--mqtt-user", type=str,
                        default=os.environ.get("MQTT_USER", "tanques"),
                        help="Usuario para autenticación en Mosquitto MQTT (default: $MQTT_USER)")
    parser.add_argument("--mqtt-password", type=str,
                        default=os.environ.get("MQTT_PASSWORD", ""),
                        help="Contraseña para autenticación en Mosquitto MQTT (default: $MQTT_PASSWORD)")

    args = parser.parse_args()

    if not args.influx_token or not args.influx_token.strip():
        logger.error(
            "ERROR DE CONFIGURACIÓN: No se configuró el token de autenticación de InfluxDB. "
            "Defina la variable de entorno INFLUX_TOKEN o use el parámetro --influx-token."
        )
        sys.exit(1)

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    influx = InfluxWriter(
        url=args.influx_url,
        token=args.influx_token,
        org=args.influx_org,
        bucket=args.influx_bucket
    )

    use_server_time = not args.use_local_timestamp

    bridge = TanquesBridge(
        influx_writer=influx,
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        mqtt_user=args.mqtt_user,
        mqtt_password=args.mqtt_password,
        command_max_age_ms=args.command_max_age_ms,
        use_server_timestamp=use_server_time,
        log_interval=args.log_every
    )

    bridge.start_mqtt()

    source = args.source
    if source == "serial" and args.serial_port:
        source = f"serial:{args.serial_port}:{args.baudrate}"
    elif source == "sim" and args.serial_port and not sys.argv[1:]:
        source = f"serial:{args.serial_port}:{args.baudrate}"

    try:
        if source.startswith("sim"):
            run_simulator_pipeline(
                bridge=bridge,
                sim_script=DEFAULT_SIM_PATH,
                config_path=args.config,
                sim_speed=args.sim_speed,
                pump_on=args.pump_on
            )
        elif source.startswith("serial:"):
            parts = source[len("serial:"):].split(":")
            port = parts[0]
            baud = int(parts[1]) if len(parts) > 1 else args.baudrate
            run_serial_pipeline(bridge=bridge, port=port, baudrate=baud)
        elif source == "stdin":
            logger.info("Leyendo líneas desde stdin...")
            for line in stream_stdin():
                bridge.process_device_line(line)
        else:
            logger.error("Fuente desconocida: %s", source)
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Bridge detenido limpiamente por el usuario.")
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
