#!/usr/bin/env python3
"""
Bridge de Telemetría Serial/Simulador -> InfluxDB 2.x (UTN FRSF / GITDA)
========================================================================
Lee tramas JSON desde el puerto serial del ESP32 o desde el simulador de tanques,
asigna el timestamp UTC oficial de ingesta (Edge Computing), formatea en InfluxDB
Line Protocol y persiste en InfluxDB 2.x.

Características de robustez:
- Desactiva DTR y RTS antes de abrir puerto serial para no reiniciar el ESP32.
- Reconexión automática con backoff exponencial ante caídas del puerto serie.
- Filtrado de líneas corruptas o no JSON.
- Admite escritura directa vía HTTP v2 /api/v2/write con soporte para InfluxDB 2.x.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional

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
    Convierte una trama JSON del contrato al Line Protocol de InfluxDB.
    
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
# Proveedores de Fuente de Datos (Serial, Simulador, Stdin)
# ==============================================================================

def stream_stdin() -> Iterator[str]:
    """Generador que lee líneas desde standard input."""
    logger.info("Leyendo tramas JSON desde stdin...")
    for line in sys.stdin:
        yield line


def stream_simulator(sim_script: str = "edge/simulator.py", extra_args: Optional[list[str]] = None) -> Iterator[str]:
    """Ejecuta el simulador en un subproceso y streamea su salida estándar."""
    cmd = [sys.executable, sim_script]
    if extra_args:
        cmd.extend(extra_args)
    logger.info("Lanzando simulador en subproceso: %s", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            yield line
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=2)


def stream_serial_with_reconnect(port: str, baudrate: int = 115200) -> Iterator[str]:
    """
    Abre el puerto serial desactivando DTR y RTS ANTES de abrirlo para evitar el reset del ESP32.
    Si la conexión se interrumpe, reconecta automáticamente con backoff exponencial.
    """
    try:
        import serial  # type: ignore
    except ImportError:
        logger.error("pyserial no está instalado. Ejecute: pip install pyserial")
        sys.exit(1)

    backoff = 1.0
    max_backoff = 30.0

    while True:
        ser: Optional[serial.Serial] = None
        try:
            logger.info("Intentando abrir puerto serial %s a %d baudios...", port, baudrate)
            # Instanciar el objeto sin abrir el descriptor para desactivar DTR/RTS primero
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = baudrate
            ser.timeout = 2.0
            ser.dtr = False  # Prevenir reset ESP32 en apertura
            ser.rts = False
            ser.open()
            
            logger.info("Puerto serial %s conectado con éxito (DTR=False, RTS=False)", port)
            backoff = 1.0  # Reset backoff tras conexión exitosa

            while ser.is_open:
                line_bytes = ser.readline()
                if not line_bytes:
                    continue  # Timeout de lectura, seguir esperando
                try:
                    line = line_bytes.decode("utf-8", errors="ignore")
                    yield line
                except Exception as dec_err:
                    logger.debug("Error decodificando línea serial: %s", dec_err)

        except (serial.SerialException, OSError) as e:
            logger.warning("Error o desconexión en puerto serial %s: %s", port, e)
        except Exception as e:
            logger.error("Error inesperado en puerto serial: %s", e)
        finally:
            if ser and ser.is_open:
                try:
                    ser.close()
                except Exception:
                    pass

        logger.info("Reintentando conexión serial en %.1f segundos...", backoff)
        time.sleep(backoff)
        backoff = min(backoff * 2.0, max_backoff)


# ==============================================================================
# Bucle Principal de Telemetría
# ==============================================================================

def run_bridge(source_spec: str, influx: InfluxWriter, sim_speed: float = 1.0) -> None:
    """Orquesta la lectura, timestamping y persistencia hacia InfluxDB."""
    if source_spec == "stdin":
        lines_iterator = stream_stdin()
    elif source_spec.startswith("sim"):
        args = ["--speed", str(sim_speed)]
        lines_iterator = stream_simulator("edge/simulator.py", extra_args=args)
    elif source_spec.startswith("serial:"):
        parts = source_spec[len("serial:"):].split(":")
        port = parts[0]
        baud = int(parts[1]) if len(parts) > 1 else 115200
        lines_iterator = stream_serial_with_reconnect(port, baud)
    else:
        logger.error("Especificación de fuente desconocida: %s", source_spec)
        sys.exit(1)

    logger.info("Iniciando pipeline de bridge hacia InfluxDB org='%s', bucket='%s'", influx.org, influx.bucket)

    for raw_line in lines_iterator:
        line = raw_line.strip()
        if not line:
            continue

        # Filtrar o descartar respuestas ack de comandos si vinieran por el mismo canal
        if '"ack"' in line:
            logger.info("[COMMAND ACK RECIBIDO] %s", line)
            continue

        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            # Ignorar líneas de log espurias o incompletas de serial
            logger.debug("Ignorando línea no JSON: %s", line)
            continue

        # ASIGNACIÓN DE TIMESTAMP OFICIAL DE INGESTA (Edge Computing)
        # Nanosegundos desde epoch UTC
        timestamp_ns = time.time_ns()
        iso_time = datetime.fromtimestamp(timestamp_ns / 1e9, tz=timezone.utc).isoformat()

        influx_line = format_influx_line(payload, timestamp_ns)
        if not influx_line:
            continue

        success = influx.write_line_protocol(influx_line)
        if success:
            logger.info(
                "[%s] Ingesta seq=%d | Tanque A: %s%% (%.1fg) | Tanque B: %s%% (%.1fg) | Bomba: %s | Q: %.2f L/min",
                iso_time,
                payload.get("seq", 0),
                payload.get("tank_a", {}).get("level_pct"),
                payload.get("tank_a", {}).get("weight_g", 0),
                payload.get("tank_b", {}).get("level_pct"),
                payload.get("tank_b", {}).get("weight_g", 0),
                payload.get("actuators", {}).get("pump"),
                payload.get("flow_lpm", 0.0)
            )
        else:
            logger.debug("No se pudo persistir la trama seq=%s en InfluxDB", payload.get("seq"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge Serial/Simulador -> InfluxDB 2.x (UTN FRSF)")
    parser.add_argument("--source", type=str, default="sim",
                        help="Fuente de datos: 'sim', 'stdin', o 'serial:<puerto>[:baud]' (ej: 'serial:COM3')")
    parser.add_argument("--sim-speed", type=float, default=1.0,
                        help="Multiplicador de velocidad si se usa --source sim (ej: 5.0)")
    parser.add_argument("--influx-url", type=str,
                        default=os.environ.get("INFLUX_URL", "http://localhost:8086"),
                        help="URL base de InfluxDB 2.x (default: http://localhost:8086)")
    parser.add_argument("--influx-token", type=str,
                        default=os.environ.get("INFLUX_TOKEN", "tanques-super-secret-token-2025"),
                        help="Token de autenticación InfluxDB 2.x")
    parser.add_argument("--influx-org", type=str,
                        default=os.environ.get("INFLUX_ORG", "utn-frsf"),
                        help="Organización en InfluxDB")
    parser.add_argument("--influx-bucket", type=str,
                        default=os.environ.get("INFLUX_BUCKET", "tanques"),
                        help="Bucket de destino en InfluxDB")

    args = parser.parse_args()

    influx = InfluxWriter(
        url=args.influx_url,
        token=args.influx_token,
        org=args.influx_org,
        bucket=args.influx_bucket
    )

    try:
        run_bridge(args.source, influx, sim_speed=args.sim_speed)
    except KeyboardInterrupt:
        logger.info("Bridge detenido limpiamente por el usuario.")


if __name__ == "__main__":
    main()
