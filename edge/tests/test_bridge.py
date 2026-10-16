"""
Tests Automatizados para el Bridge Bidireccional (UTN FRSF / GITDA)
===================================================================
Verifica:
1. Comando válido -> encolado al dispositivo y publicación de ack exitoso en MQTT.
2. Ack con interlock -> publicación correcta en 'tanques/ack' con motivo (reason).
3. Timeout de dispositivo (device_timeout) -> 2.5 s sin respuesta del equipo emite falla.
4. Comando expirado -> antigüedad > 5 s según campo 'ts' se descarta y emite 'expired'.
5. Comando duplicado -> deduplicación por 'id' en ventana deslizante emite 'duplicate'.
6. Líneas no JSON -> filtradas y descartadas sin crashear.
7. Separación de contenido -> telemetría enviada a InfluxDB y acks enviados a MQTT.
8. Resiliencia de reconexión MQTT -> suscripción en on_connect con QoS 1 y sin caídas fatales.
"""

import json
import queue
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from edge.bridge import TanquesBridge, format_influx_line


class FakeMqttClient:
    """Mock liviano para interceptar publicaciones y suscripciones MQTT."""

    def __init__(self) -> None:
        self.published_messages: List[Dict[str, Any]] = []
        self.subscriptions: List[tuple[str, int]] = []
        self.on_connect = None
        self.on_disconnect = None
        self.on_message = None

    def publish(self, topic: str, payload: bytes, qos: int = 1, retain: bool = False) -> None:
        self.published_messages.append({
            "topic": topic,
            "payload": json.loads(payload.decode("utf-8")),
            "qos": qos,
            "retain": retain
        })

    def subscribe(self, topic: str, qos: int = 1) -> None:
        self.subscriptions.append((topic, qos))

    def connect_async(self, host: str, port: int, keepalive: int = 60) -> None:
        pass

    def loop_start(self) -> None:
        pass

    def loop_stop(self) -> None:
        pass

    def disconnect(self) -> None:
        pass


@pytest.fixture
def fake_mqtt() -> FakeMqttClient:
    return FakeMqttClient()


@pytest.fixture
def bridge(fake_mqtt: FakeMqttClient) -> TanquesBridge:
    # Bridge con cliente MQTT simulado y timeout rápido para tests
    b = TanquesBridge(
        influx_writer=None,
        mqtt_client=fake_mqtt,
        cmd_timeout_s=0.2,  # 200 ms para pruebas veloces y deterministas
        max_cmd_age_s=5.0,
        dedup_window_size=50
    )
    yield b
    b.stop()


def test_valid_command_forwarding_and_ack(bridge: TanquesBridge, fake_mqtt: FakeMqttClient) -> None:
    """1. Un comando válido se encola hacia el serial y al recibir ack del equipo se publica en MQTT."""
    cmd_id = "test-cmd-001"
    now_ms = int(time.time() * 1000)
    cmd = {
        "id": cmd_id,
        "cmd": "set",
        "target": "pump",
        "value": True,
        "ts": now_ms
    }

    # Simular mensaje MQTT recibido en tanques/cmd
    bridge.handle_incoming_command(json.dumps(cmd))

    # Verificar que el comando fue encolado para el equipo físico
    assert not bridge.command_queue.empty()
    queued_cmd = json.loads(bridge.command_queue.get_nowait())
    assert queued_cmd["id"] == cmd_id
    assert queued_cmd["value"] is True

    # Simular que el microcontrolador responde por serial con ack exitoso
    device_response = json.dumps({"ack": cmd_id, "ok": True})
    bridge.process_device_line(device_response)

    # Verificar que se publicó en tanques/ack con QoS 1 y retain=False
    assert len(fake_mqtt.published_messages) == 1
    msg = fake_mqtt.published_messages[0]
    assert msg["topic"] == "tanques/ack"
    assert msg["qos"] == 1
    assert msg["retain"] is False
    assert msg["payload"]["ack"] == cmd_id
    assert msg["payload"]["ok"] is True


def test_command_interlock_ack(bridge: TanquesBridge, fake_mqtt: FakeMqttClient) -> None:
    """2. Si el hardware rechaza el comando por interlock, el ack se publica con el reason correspondiente."""
    cmd_id = "test-cmd-002"
    now_ms = int(time.time() * 1000)
    cmd = {"id": cmd_id, "cmd": "set", "target": "pump", "value": True, "ts": now_ms}

    bridge.handle_incoming_command(json.dumps(cmd))
    _ = bridge.command_queue.get_nowait()

    # Simular rechazo de interlock por sobrellenado en Tanque A
    device_response = json.dumps({"ack": cmd_id, "ok": False, "reason": "overflow_a"})
    bridge.process_device_line(device_response)

    assert len(fake_mqtt.published_messages) == 1
    msg = fake_mqtt.published_messages[0]
    assert msg["payload"]["ack"] == cmd_id
    assert msg["payload"]["ok"] is False
    assert msg["payload"]["reason"] == "overflow_a"


def test_device_timeout(bridge: TanquesBridge, fake_mqtt: FakeMqttClient) -> None:
    """3. Si el dispositivo no responde dentro del timeout (0.2s en test), se emite 'device_timeout'."""
    cmd_id = "test-cmd-timeout"
    now_ms = int(time.time() * 1000)
    cmd = {"id": cmd_id, "cmd": "set", "target": "pump", "value": True, "ts": now_ms}

    bridge.handle_incoming_command(json.dumps(cmd))

    # Esperar a que expire el timer de 0.2 s
    time.sleep(0.35)

    assert len(fake_mqtt.published_messages) == 1
    msg = fake_mqtt.published_messages[0]
    assert msg["payload"]["ack"] == cmd_id
    assert msg["payload"]["ok"] is False
    assert msg["payload"]["reason"] == "device_timeout"

    # Si el dispositivo respondiera tarde, ese ack tardío ya no debe duplicar
    bridge.process_device_line(json.dumps({"ack": cmd_id, "ok": True}))
    # Se ignora o no genera un nuevo ack inconsistente
    assert len(fake_mqtt.published_messages) == 2  # Publica el ack crudo informativo pero sin timer activo


def test_expired_command(bridge: TanquesBridge, fake_mqtt: FakeMqttClient) -> None:
    """4. Si un comando tiene más de 5 s de antigüedad, se descarta sin enviar al serial."""
    cmd_id = "test-cmd-expired"
    # Timestamp de hace 10 segundos
    old_ts = int((time.time() - 10.0) * 1000)
    cmd = {"id": cmd_id, "cmd": "set", "target": "pump", "value": True, "ts": old_ts}

    bridge.handle_incoming_command(json.dumps(cmd))

    # No debe haberse encolado hacia el serial
    assert bridge.command_queue.empty()

    # Debe haberse emitido ack de rechazo por 'expired'
    assert len(fake_mqtt.published_messages) == 1
    msg = fake_mqtt.published_messages[0]
    assert msg["payload"]["ack"] == cmd_id
    assert msg["payload"]["ok"] is False
    assert msg["payload"]["reason"] == "expired"


def test_duplicate_command(bridge: TanquesBridge, fake_mqtt: FakeMqttClient) -> None:
    """5. Un comando con un 'id' ya procesado en la ventana se rechaza como duplicado."""
    cmd_id = "test-cmd-dup"
    now_ms = int(time.time() * 1000)
    cmd = {"id": cmd_id, "cmd": "set", "target": "pump", "value": True, "ts": now_ms}

    # Primer envío
    bridge.handle_incoming_command(json.dumps(cmd))
    assert not bridge.command_queue.empty()
    _ = bridge.command_queue.get_nowait()

    # Segundo envío idéntico
    bridge.handle_incoming_command(json.dumps(cmd))

    # La cola no debe tener nada nuevo
    assert bridge.command_queue.empty()

    # Se debió publicar ack con motivo 'duplicate'
    assert len(fake_mqtt.published_messages) == 1
    msg = fake_mqtt.published_messages[0]
    assert msg["payload"]["ack"] == cmd_id
    assert msg["payload"]["ok"] is False
    assert msg["payload"]["reason"] == "duplicate"


def test_non_json_lines_ignored(bridge: TanquesBridge, fake_mqtt: FakeMqttClient) -> None:
    """6. Las líneas no JSON del bootloader o ruido serial no provocan excepciones."""
    noisy_lines = [
        "Arduino Uno R3 Booting...",
        "--- START SERIAL LOG ---",
        "{broken json: true,",
        " \t \n",
        "random noise byte: \x00\x01\xfe"
    ]

    for noisy in noisy_lines:
        bridge.process_device_line(noisy)

    # Nada fue enviado a MQTT ni causó error
    assert len(fake_mqtt.published_messages) == 0


def test_telemetry_and_ack_separation(fake_mqtt: FakeMqttClient) -> None:
    """7. El bridge discrimina correctamente entre tramas periódicas de telemetría y acks de comandos."""
    mock_influx = MagicMock()
    mock_influx.write_line_protocol.return_value = True

    b = TanquesBridge(influx_writer=mock_influx, mqtt_client=fake_mqtt, cmd_timeout_s=1.0)

    # Simular una trama de telemetría
    telemetry_line = json.dumps({
        "v": 1,
        "seq": 100,
        "uptime_ms": 50000,
        "tank_a": {"weight_g": 1200.0, "level_pct": 30.0, "temp_c": 24.0},
        "tank_b": {"weight_g": 800.0, "level_pct": 20.0, "temp_c": 23.5},
        "flow_lpm": 1.8,
        "actuators": {"pump": True},
        "alarms": {"overflow_a": False, "overflow_b": False, "sensor_fault": False},
        "mode": "auto"
    })

    b.process_device_line(telemetry_line)

    # InfluxWriter debió recibir la escritura
    assert mock_influx.write_line_protocol.called
    assert b.telemetry_success_count == 1
    # MQTT no debió recibir ningún ack
    assert len(fake_mqtt.published_messages) == 0

    # Ahora procesamos un ack
    ack_line = json.dumps({"ack": "cmd-xyz", "ok": True})
    b.process_device_line(ack_line)

    # MQTT recibe el ack
    assert len(fake_mqtt.published_messages) == 1
    assert fake_mqtt.published_messages[0]["payload"]["ack"] == "cmd-xyz"
    b.stop()


def test_mqtt_connection_and_reconnection_resilience() -> None:
    """8. Al conectar al broker MQTT se suscribe a tanques/cmd con QoS 1; no falla con broker caído."""
    fake_client = FakeMqttClient()
    b = TanquesBridge(mqtt_client=fake_client)

    # Simular llamada a on_connect exitoso (reason_code=0)
    b._on_mqtt_connect(fake_client, None, None, 0)
    assert ("tanques/cmd", 1) in fake_client.subscriptions

    # Simular desconexión
    b._on_mqtt_disconnect(fake_client, None, None, 7)
    # No lanza excepciones
    b.stop()


def test_end_to_end_with_simulator(fake_mqtt: FakeMqttClient) -> None:
    """9. Prueba de integración de punta a punta con el simulador real en subproceso."""
    import threading
    from edge.bridge import DEFAULT_CONFIG_PATH, DEFAULT_SIM_PATH, run_simulator_pipeline

    mock_influx = MagicMock()
    mock_influx.write_line_protocol.return_value = True

    b = TanquesBridge(influx_writer=mock_influx, mqtt_client=fake_mqtt, cmd_timeout_s=3.0)

    sim_thread = threading.Thread(
        target=run_simulator_pipeline,
        kwargs={
            "bridge": b,
            "sim_script": DEFAULT_SIM_PATH,
            "config_path": DEFAULT_CONFIG_PATH,
            "sim_speed": 5.0,
            "pump_on": False
        },
        daemon=True
    )
    sim_thread.start()

    try:
        # Esperar a que el simulador arranque y envíe al menos 1 trama
        t0 = time.time()
        while time.time() - t0 < 6.0 and b.telemetry_success_count == 0:
            time.sleep(0.1)

        assert b.telemetry_success_count > 0, "No se recibió telemetría del simulador a tiempo"

        # Enviar comando de encendido de bomba por MQTT
        cmd_id = "e2e-pump-on"
        now_ms = int(time.time() * 1000)
        cmd = {"id": cmd_id, "cmd": "set", "target": "pump", "value": True, "ts": now_ms}
        b.handle_incoming_command(json.dumps(cmd))

        # Esperar a que el simulador procese por stdin y devuelva el ack por stdout
        t1 = time.time()
        while time.time() - t1 < 4.0 and not fake_mqtt.published_messages:
            time.sleep(0.1)

        assert len(fake_mqtt.published_messages) >= 1
        ack_msg = fake_mqtt.published_messages[0]
        assert ack_msg["topic"] == "tanques/ack"
        assert ack_msg["payload"]["ack"] == cmd_id
        assert ack_msg["payload"]["ok"] is True

    finally:
        b.stop()
