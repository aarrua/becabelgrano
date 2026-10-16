#!/usr/bin/env python3
"""
Bridge de Telemetría y Control Bidireccional: Serial/Simulador <-> MQTT / InfluxDB 2.x
====================================================================================
Universidad Tecnológica Nacional - Facultad Regional Santa Fe (UTN FRSF / GITDA)

Funciones del Bridge:
1. Ingesta de Telemetría:
   Lee tramas JSON desde el puerto serial del microcontrolador (o simulador de tanques),
   asigna el timestamp UTC oficial de ingesta (Edge Computing), formatea a Line Protocol
   y persiste en InfluxDB 2.x.
2. Canal Bidireccional de Comandos (MQTT <-> Serial):
   - Se suscribe al tópico 'tanques/cmd' (QoS 1) en broker Mosquitto.
   - Seguridad y validación: rechaza comandos expirados (> 5 s de antigüedad según campo 'ts')
     y deduplica por 'id' en una ventana deslizante de N elementos.
   - Despacha los comandos válidos hacia el puerto serial (o stdin del simulador) mediante
     una cola secuencial, manteniendo un único hilo lector dueño del puerto.
   - Correlación asíncrona por 'id': si el equipo físico responde en < 2.5 s, publica el
     resultado en 'tanques/ack' (QoS 1). Si vence el timeout, emite 'device_timeout'.
3. Resiliencia en el Borde:
   - Desactiva DTR y RTS antes de abrir el puerto serial para evitar el reset del ESP32/Arduino.
   - Reconexión automática con backoff exponencial ante caídas del puerto serie y del broker MQTT.
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
from typing import Any, Callable, Deque, Dict, Iterator, Optional, Set

try:
    import paho.mqtt.client as mqtt  # type: ignore
except ImportError:
    mqtt = None  # Se validará en tiempo de ejecución

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
        self.url = url.rstrip("/")
        self.token = token
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


def format_influx_line(data: Dict[str, Any], timestamp_ns: int) -> Optional[str]:
    """
    Convierte una trama JSON de telemetría al Line Protocol de InfluxDB.
    
    Measurement: telemetry
    Tags: mode=<auto|manual>
    Fields: seq, uptime_ms, tank_a_*, tank_b_*, flow_lpm, pump, overflow_a, overflow_b, sensor_fault
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
        flow_lpm = float(data.get("flow_lpm", 0.0))
        actuators = data.get("actuators", {})
        alarms = data.get("alarms", {})

        fields = [
            f"seq={seq}i",
            f"uptime_ms={uptime_ms}i",
            f"tank_a_weight_g={float(tank_a['weight_g']):.2f}",
            f"tank_a_level_pct={float(tank_a['level_pct']):.2f}",
            f"tank_a_temp_c={float(tank_a['temp_c']):.2f}",
            f"tank_b_weight_g={float(tank_b['weight_g']):.2f}",
            f"tank_b_level_pct={float(tank_b['level_pct']):.2f}",
            f"tank_b_temp_c={float(tank_b['temp_c']):.2f}",
            f"flow_lpm={flow_lpm:.2f}",
            f"pump={'true' if actuators.get('pump', False) else 'false'}",
            f"overflow_a={'true' if alarms.get('overflow_a', False) else 'false'}",
            f"overflow_b={'true' if alarms.get('overflow_b', False) else 'false'}",
            f"sensor_fault={'true' if alarms.get('sensor_fault', False) else 'false'}",
        ]

        # Formato: measurement,tag=val field=val,field=val timestamp
        line = f"telemetry,mode={mode} {','.join(fields)} {timestamp_ns}"
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
        max_cmd_age_s: float = 5.0,
        dedup_window_size: int = 100,
        log_interval: int = 30,
        mqtt_client: Optional[Any] = None,
    ) -> None:
        self.influx_writer = influx_writer
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_password = mqtt_password
        self.cmd_topic = cmd_topic
        self.ack_topic = ack_topic
        self.cmd_timeout_s = cmd_timeout_s
        self.max_cmd_age_s = max_cmd_age_s
        self.log_interval = log_interval

        # Deduplicación de comandos en ventana deslizante
        self.dedup_window_size = dedup_window_size
        self._dedup_deque: Deque[str] = collections.deque(maxlen=dedup_window_size)
        self._dedup_set: Set[str] = set()

        # Comandos pendientes de ack: {cmd_id: {"timer": Timer, "created_at": float}}
        self._pending_commands: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

        # Cola de comandos hacia el hardware/simulador
        self.command_queue: queue.Queue[str] = queue.Queue()

        # Métricas y estado
        self.telemetry_success_count = 0
        self.running = True

        # Inicialización de cliente MQTT
        self.mqtt_client = mqtt_client
        if self.mqtt_client is None and mqtt is not None:
            self._init_mqtt_client()

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
            logger.error("Error al iniciar cliente MQTT: %s. Reintentos automáticos habilitados.", e)

    def stop(self) -> None:
        """Detiene el bridge y libera recursos."""
        self.running = False
        with self._lock:
            for item in self._pending_commands.values():
                timer: threading.Timer = item.get("timer")
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
        # En CallbackAPIVersion.VERSION2, reason_code == 0 indica conexión exitosa
        if reason_code == 0:
            logger.info("✓ Conectado exitosamente a Mosquitto (%s:%d). Suscribiendo a '%s' (QoS 1)...",
                        self.mqtt_host, self.mqtt_port, self.cmd_topic)
            client.subscribe(self.cmd_topic, qos=1)
        else:
            logger.warning("Falla al conectar con broker MQTT: %s", reason_code)

    def _on_mqtt_disconnect(self, client: Any, userdata: Any, disconnect_flags: Any, reason_code: Any, properties: Any = None) -> None:
        """Callback invocado ante desconexión del broker MQTT."""
        logger.warning("Desconexión de Mosquitto (%s). El cliente intentará reconectar automáticamente con backoff.", reason_code)

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
        - Timestamp (ts): si supera max_cmd_age_s (5 s), responde 'expired'.
        - Deduplicación por 'id' en ventana deslizante.
        - Si es válido, lo encola para envío serial y programa el timeout de 2.5 s.
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

        # 1. Validación de Expiración por Timestamp (ts)
        now_epoch_ms = int(time.time() * 1000)
        cmd_ts = cmd.get("ts")
        if isinstance(cmd_ts, (int, float)):
            age_s = (now_epoch_ms - cmd_ts) / 1000.0
            if age_s > self.max_cmd_age_s:
                logger.warning("Comando id='%s' EXPIRADO (antigüedad: %.2f s > %.1f s). No se envía al hardware.",
                               cmd_id, age_s, self.max_cmd_age_s)
                self.publish_ack({"ack": cmd_id, "ok": False, "reason": "expired"})
                return

        # 2. Deduplicación por 'id'
        with self._lock:
            if cmd_id in self._dedup_set:
                logger.warning("Comando id='%s' DUPLICADO ignorado (ya procesado en la ventana actual).", cmd_id)
                self.publish_ack({"ack": cmd_id, "ok": False, "reason": "duplicate"})
                return

            # Agregar a la ventana deslizante
            if len(self._dedup_deque) >= self.dedup_window_size:
                oldest_id = self._dedup_deque.popleft()
                self._dedup_set.discard(oldest_id)
            self._dedup_deque.append(cmd_id)
            self._dedup_set.add(cmd_id)

            # 3. Registrar comando pendiente y programar timer de 2.5 s
            timer = threading.Timer(self.cmd_timeout_s, self._handle_command_timeout, args=(cmd_id,))
            timer.daemon = True
            self._pending_commands[cmd_id] = {
                "timer": timer,
                "created_at": time.time(),
                "raw_cmd": cmd
            }
            timer.start()

        # 4. Encolar comando serial
        logger.info("Comando id='%s' validado y encolado hacia el equipo físico: %s", cmd_id, payload_str)
        self.command_queue.put(payload_str)

    def _handle_command_timeout(self, cmd_id: str) -> None:
        """Callback ejecutado si el microcontrolador no responde en 2.5 segundos."""
        with self._lock:
            if cmd_id not in self._pending_commands:
                return
            del self._pending_commands[cmd_id]

        logger.error("TIMEOUT: El equipo no respondió al comando id='%s' en %.1f s. Emitiendo 'device_timeout'.",
                     cmd_id, self.cmd_timeout_s)
        self.publish_ack({"ack": cmd_id, "ok": False, "reason": "device_timeout"})

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
        Procesa una línea cruda recibida desde el microcontrolador o simulador:
        - Si no es JSON o está corrupta: se ignora sin crashear.
        - Si contiene el campo 'ack': se resuelve el comando pendiente y se publica en MQTT.
        - Si es telemetría: se añade timestamp UTC oficial y se persiste en InfluxDB.
        """
        line = raw_line.strip()
        if not line:
            return

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            # El Arduino Uno emite texto de bootloader o ruido serial al resetear
            logger.debug("Línea ignorada (no es JSON): %s", line)
            return

        if not isinstance(data, dict):
            logger.debug("Línea JSON descartada (no es objeto dict): %s", line)
            return

        # ----------------------------------------------------------------------
        # Caso A: Respuesta ACK de un comando
        # ----------------------------------------------------------------------
        if "ack" in data:
            ack_id = str(data["ack"])
            with self._lock:
                pending = self._pending_commands.pop(ack_id, None)
                if pending:
                    timer: threading.Timer = pending.get("timer")
                    if timer:
                        timer.cancel()
                    elapsed = time.time() - pending.get("created_at", time.time())
                    logger.info("✓ ACK recibido del equipo para id='%s' (tiempo: %.3f s): ok=%s",
                                ack_id, elapsed, data.get("ok"))
                else:
                    logger.warning("ACK recibido para comando id='%s' desconocido o ya expirado.", ack_id)

            # Publicar el ack tal como vino en el canal MQTT
            self.publish_ack(data)
            return

        # ----------------------------------------------------------------------
        # Caso B: Trama periódica de Telemetría
        # ----------------------------------------------------------------------
        timestamp_ns = time.time_ns()
        iso_time = datetime.fromtimestamp(timestamp_ns / 1e9, tz=timezone.utc).isoformat()

        if not self.influx_writer:
            return

        influx_line = format_influx_line(data, timestamp_ns)
        if not influx_line:
            return

        success = self.influx_writer.write_line_protocol(influx_line)
        if success:
            self.telemetry_success_count += 1
            if self.log_interval > 0 and self.telemetry_success_count % self.log_interval == 0:
                logger.info(
                    "[%s] InfluxDB: %d tramas persistidas acumuladas (última seq=%d | A: %s%% | B: %s%% | Bomba: %s | Q: %.2f L/min)",
                    iso_time,
                    self.telemetry_success_count,
                    data.get("seq", 0),
                    data.get("tank_a", {}).get("level_pct"),
                    data.get("tank_b", {}).get("level_pct"),
                    data.get("actuators", {}).get("pump"),
                    data.get("flow_lpm", 0.0)
                )


# ==============================================================================
# Hilos de Comunicación con el Hardware (Serial o Simulador)
# ==============================================================================

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
            # Desactivar líneas de control antes de abrir para evitar reset del Arduino/ESP32
            ser.dtr = False
            ser.rts = False
            ser.open()

            logger.info("✓ Puerto serial %s conectado exitosamente.", port)
            backoff = 1.0  # Reset de backoff

            # Hilo escritor que toma comandos de la cola y los escribe al serial
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

            # Bucle lector exclusivo del puerto
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
    sim_script: Optional[Path | str] = None,
    config_path: Optional[Path | str] = None,
    sim_speed: float = 1.0,
    pump_on: bool = False,
) -> None:
    """
    Ejecuta el simulador en un subproceso con comunicación bidireccional:
    - stdin conectado para recibir comandos.
    - stdout leído por el hilo lector del bridge.
    - Reconexión y respawn automático ante caídas del subproceso.
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

            # Hilo escritor hacia el stdin del simulador
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

            # Bucle lector de stdout del simulador
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

    # InfluxDB
    parser.add_argument("--influx-url", type=str,
                        default=os.environ.get("INFLUX_URL", "http://localhost:8086"),
                        help="URL base de InfluxDB 2.x")
    parser.add_argument("--influx-token", type=str,
                        default=os.environ.get("INFLUX_TOKEN", "tanques-super-secret-token-2025"),
                        help="Token de autenticación InfluxDB 2.x")
    parser.add_argument("--influx-org", type=str,
                        default=os.environ.get("INFLUX_ORG", "utn-frsf"),
                        help="Organización en InfluxDB")
    parser.add_argument("--influx-bucket", type=str,
                        default=os.environ.get("INFLUX_BUCKET", "tanques"),
                        help="Bucket de destino en InfluxDB")

    # Mosquitto MQTT
    parser.add_argument("--mqtt-host", type=str,
                        default=os.environ.get("MQTT_HOST", "localhost"),
                        help="Host del broker Mosquitto MQTT (default: localhost)")
    parser.add_argument("--mqtt-port", type=int,
                        default=int(os.environ.get("MQTT_PORT", "1883")),
                        help="Puerto del broker Mosquitto MQTT (default: 1883)")
    parser.add_argument("--mqtt-user", type=str,
                        default=os.environ.get("MQTT_USER", "tanques"),
                        help="Usuario para autenticación en Mosquitto MQTT")
    parser.add_argument("--mqtt-password", type=str,
                        default=os.environ.get("MQTT_PASSWORD", ""),
                        help="Contraseña para autenticación en Mosquitto MQTT")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    influx = InfluxWriter(
        url=args.influx_url,
        token=args.influx_token,
        org=args.influx_org,
        bucket=args.influx_bucket
    )

    bridge = TanquesBridge(
        influx_writer=influx,
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        mqtt_user=args.mqtt_user,
        mqtt_password=args.mqtt_password,
        log_interval=args.log_every
    )

    # Iniciar conexión asíncrona MQTT
    bridge.start_mqtt()

    # Determinar fuente de datos
    source = args.source
    if source == "serial" and args.serial_port:
        source = f"serial:{args.serial_port}:{args.baudrate}"
    elif source == "sim" and args.serial_port and not sys.argv[1:]:
        # Si se definió SERIAL_PORT por entorno y no se especificó --source explícito
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
            logger.info("Leyendo líneas desde stdin (modo unidireccional)...")
            for line in sys.stdin:
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
