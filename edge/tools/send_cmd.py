#!/usr/bin/env python3
"""
Herramienta de Diagnóstico: Envío de Comandos de Prueba por MQTT (UTN FRSF / GITDA)
==================================================================================
Publica un comando de control estructurado en el tópico 'tanques/cmd' (QoS 1).
Permite configurar el ID del comando, el valor del actuador (bomba) y una edad
artificial para simular comandos normales o expirados.

Uso:
    python edge/tools/send_cmd.py <id> <true|false> [edad_segundos] [target]

Ejemplos:
    # Encender bomba con timestamp fresco (0 s)
    python edge/tools/send_cmd.py cmd-1 true

    # Apagar bomba con comando de 10 segundos de antigüedad (debe expirar en el bridge)
    python edge/tools/send_cmd.py cmd-viejo false 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict

try:
    import paho.mqtt.client as mqtt  # type: ignore
except ImportError:
    print("Error: paho-mqtt no está instalado. Ejecute: pip install paho-mqtt==2.1.0", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publica comandos de prueba en 'tanques/cmd' para probar el Bridge y microcontrolador."
    )
    parser.add_argument("id", type=str, help="Identificador único del comando (ej: cmd-101)")
    parser.add_argument("value", type=str, help="Valor del actuador: 'true'/'1'/'on' o 'false'/'0'/'off'")
    parser.add_argument("age_s", type=float, nargs="?", default=0.0,
                        help="Antigüedad artificial en segundos respecto a la hora actual (default: 0.0)")
    parser.add_argument("--target", type=str, default="pump",
                        help="Actuador de destino (default: 'pump')")
    parser.add_argument("--host", type=str, default=os.environ.get("MQTT_HOST", "localhost"),
                        help="Host del broker Mosquitto (default: localhost o MQTT_HOST)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MQTT_PORT", "1883")),
                        help="Puerto MQTT (default: 1883 o MQTT_PORT)")
    parser.add_argument("--user", type=str, default=os.environ.get("MQTT_USER", "tanques"),
                        help="Usuario MQTT (default: tanques o MQTT_USER)")
    parser.add_argument("--password", type=str, default=os.environ.get("MQTT_PASSWORD", ""),
                        help="Contraseña MQTT (default: valor de variable MQTT_PASSWORD)")

    args = parser.parse_args()

    val_str = args.value.strip().lower()
    if val_str in ("true", "1", "on", "yes", "si", "sí"):
        actuator_value = True
    elif val_str in ("false", "0", "off", "no"):
        actuator_value = False
    else:
        print(f"Error: valor booleano no reconocido '{args.value}'. Use 'true' o 'false'.", file=sys.stderr)
        sys.exit(1)

    now_epoch_ms = int(time.time() * 1000)
    cmd_ts = int(now_epoch_ms - (args.age_s * 1000.0))

    payload: Dict[str, Any] = {
        "id": args.id,
        "cmd": "set",
        "target": args.target,
        "value": actuator_value,
        "ts": cmd_ts
    }

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"send-cmd-tool-{os.getpid()}",
        clean_session=True
    )

    if args.user and args.password:
        client.username_pw_set(args.user, args.password)

    try:
        client.connect(args.host, args.port, keepalive=10)
        client.loop_start()

        payload_bytes = json.dumps(payload).encode("utf-8")
        msg_info = client.publish("tanques/cmd", payload_bytes, qos=1, retain=False)
        msg_info.wait_for_publish(timeout=3.0)

        client.loop_stop()
        client.disconnect()

        print(f"✓ Comando publicado con éxito en 'tanques/cmd' (QoS 1):")
        print(f"  {json.dumps(payload)}")
    except Exception as e:
        print(f"Error publicando comando en MQTT ({args.host}:{args.port}): {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
