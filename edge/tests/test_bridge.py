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
import logging
import queue
import time
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest

from edge.bridge import RealFlowReader, TanquesBridge, format_influx_line


class FakeMqttClient:
    """Mock liviano para interceptar publicaciones y suscripciones MQTT."""

    def __init__(self) -> None:
        self.published_messages: List[Dict[str, Any]] = []
        self.subscriptions: List[Tuple[str, int]] = []
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
        command_max_age_ms=5000,
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
    """5. Comandos duplicados: republica el ack original si ya se resolvió, o ignora en silencio si está pendiente."""
    cmd_id = "test-cmd-dup"
    now_ms = int(time.time() * 1000)
    cmd = {"id": cmd_id, "cmd": "set", "target": "pump", "value": True, "ts": now_ms}

    # Escenario A: El comando ingresa y es despachado
    bridge.handle_incoming_command(json.dumps(cmd))
    assert not bridge.command_queue.empty()
    _ = bridge.command_queue.get_nowait()

    # El dispositivo responde con ACK exitoso
    device_response = json.dumps({"ack": cmd_id, "ok": True})
    bridge.process_device_line(device_response)

    assert len(fake_mqtt.published_messages) == 1
    assert fake_mqtt.published_messages[0]["payload"]["ack"] == cmd_id
    assert fake_mqtt.published_messages[0]["payload"]["ok"] is True

    # Reintento idéntico del mismo comando (duplicado tras resolución)
    bridge.handle_incoming_command(json.dumps(cmd))

    # La cola hacia el dispositivo no debe recibir nada nuevo
    assert bridge.command_queue.empty()

    # Se debió REPUBLICAR el ack original guardado (ok=True), NUNCA un ack de fallo ("duplicate")
    assert len(fake_mqtt.published_messages) == 2
    republished = fake_mqtt.published_messages[1]
    assert republished["payload"]["ack"] == cmd_id
    assert republished["payload"]["ok"] is True
    assert "reason" not in republished["payload"]

    # Escenario B: Duplicado recibido mientras el comando aún está pendiente en serial
    cmd_pending_id = "test-cmd-pending"
    cmd_pending = {"id": cmd_pending_id, "cmd": "set", "target": "pump", "value": False, "ts": now_ms}

    bridge.handle_incoming_command(json.dumps(cmd_pending))
    assert not bridge.command_queue.empty()
    _ = bridge.command_queue.get_nowait()

    # Se envía duplicado ANTES de que el hardware responda
    messages_count_before = len(fake_mqtt.published_messages)
    bridge.handle_incoming_command(json.dumps(cmd_pending))

    # No se encola nada extra y se ignora en silencio sin publicar fallo
    assert bridge.command_queue.empty()
    assert len(fake_mqtt.published_messages) == messages_count_before


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


def test_mqtt_broker_down_at_startup() -> None:
    """10. Si el broker MQTT está caído al arrancar, connect_async no crashea y el bridge opera."""
    b = TanquesBridge(
        mqtt_host="127.0.0.1",
        mqtt_port=18839,  # Puerto donde no hay broker escuchando
        cmd_timeout_s=1.0
    )
    # start_mqtt no debe lanzar excepciones no controladas
    b.start_mqtt()
    assert b.running is True
    # Telemetría y líneas recibidas se procesan con normalidad sin crashear
    b.process_device_line("Línea de prueba sin crasheo")
    b.stop()


def test_bridge_aborts_when_influx_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """11. Si INFLUX_TOKEN no está definido, el bridge aborta con código 1."""
    import sys
    from edge.bridge import main
    monkeypatch.delenv("INFLUX_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["bridge.py", "--source", "sim"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_influx_writer_raises_when_token_empty() -> None:
    """12. InfluxWriter lanza ValueError si el token es nulo o vacío."""
    from edge.bridge import InfluxWriter
    with pytest.raises(ValueError, match="Token de autenticación InfluxDB"):
        InfluxWriter(url="http://localhost:8086", token="", org="utn-frsf", bucket="tanques")


def test_format_influx_line_with_null_sensors() -> None:
    """13. Tramas con valores nulos (MODO_SIM_SIN_SENSORES o sensor_fault) se formatean correctamente."""
    trama = {
        "v": 1,
        "seq": 42,
        "uptime_ms": 12000,
        "tank_a": {"weight_g": None, "level_pct": None, "temp_c": None},
        "tank_b": {"weight_g": None, "level_pct": None, "temp_c": None},
        "flow_lpm": None,
        "actuators": {"pump": True},
        "alarms": {"overflow_a": False, "overflow_b": False, "sensor_fault": True},
        "mode": "auto"
    }
    line = format_influx_line(trama)
    assert line is not None
    assert line.startswith("telemetry,mode=auto")
    assert "seq=42i" in line
    assert "uptime_ms=12000i" in line
    assert "pump=true" in line
    assert "sensor_fault=true" in line
    assert "tank_a_weight_g" not in line


def test_process_device_line_with_null_sensors_logging(caplog: pytest.LogCaptureFixture) -> None:
    """14. Tramas con sensores o actuadores en null no fallan en los logs periódicos del bridge."""
    import logging
    mock_writer = MagicMock()
    mock_writer.write_line_protocol.return_value = True

    bridge = TanquesBridge(
        influx_writer=mock_writer,
        log_interval=1  # Loggea en cada trama exitosa
    )

    trama_uno_sin_sensores = {
        "v": 1,
        "seq": 1,
        "uptime_ms": 1050,
        "tank_a": {"level_pct": None, "weight_g": None, "temp_c": None},
        "tank_b": {"level_pct": None, "weight_g": None, "temp_c": None},
        "flow_lpm": None,
        "actuators": {"pump": False},
        "alarms": {"tank_a_sensor_fault": True, "tank_b_sensor_fault": True, "temp_sensor_fault": True, "leak_detected": False}
    }

    trama_con_nulos_y_pump_nula = {
        "v": 1,
        "seq": 2,
        "uptime_ms": 2100,
        "tank_a": {"level_pct": None, "weight_g": None, "temp_c": None},
        "tank_b": {"level_pct": None, "weight_g": None, "temp_c": None},
        "flow_lpm": None,
        "actuators": {"pump": None},
        "alarms": {"sensor_fault": True}
    }

    with caplog.at_level(logging.INFO, logger="edge-bridge"):
        # Trama 1: Modo sin sensores típico de Arduino Uno
        bridge.process_device_line(json.dumps(trama_uno_sin_sensores))
        assert bridge.telemetry_success_count == 1
        assert "A: s/d" in caplog.text
        assert "B: s/d" in caplog.text
        assert "Q: s/d" in caplog.text
        assert "Bomba: False" in caplog.text
        assert "seq=1" in caplog.text

        # Trama 2: Sensores y bomba en null
        bridge.process_device_line(json.dumps(trama_con_nulos_y_pump_nula))
        assert bridge.telemetry_success_count == 2
        assert "seq=2" in caplog.text
        assert "Bomba: s/d" in caplog.text




@pytest.mark.parametrize("cmd", [
    {"id": "cal-tare-a", "cmd": "tare", "tank": "a"},
    {"id": "cal-scale-a", "cmd": "cal_scale", "tank": "a", "scale": 415.8},
    {"id": "cal-reset", "cmd": "reset_cal"},
    {"id": "cal-save", "cmd": "save_cal"},
    {"id": "cal-cap-a", "cmd": "set_capacity", "tank": "a", "grams": 4000.0},
    {"id": "cal-cap-b", "cmd": "set_capacity", "tank": "b", "grams": 2450.0},
    {"id": "cal-flow", "cmd": "cal_flow", "pulses_per_l": 450.0},
])
def test_calibration_commands_pass_through_to_serial(bridge: TanquesBridge, cmd: Dict[str, Any]) -> None:
    """Los comandos de calibracion (tare, cal_scale, set_capacity, cal_flow, reset_cal, save_cal) con id se reenvian tal cual al serial."""
    bridge.handle_incoming_command(json.dumps(cmd))

    assert not bridge.command_queue.empty()
    assert json.loads(bridge.command_queue.get_nowait()) == cmd


def test_calibration_command_without_id_is_discarded(bridge: TanquesBridge) -> None:
    """Un comando de calibracion sin id se descarta y no llega al serial."""
    bridge.handle_incoming_command(json.dumps({"cmd": "save_cal"}))

    assert bridge.command_queue.empty()


def test_calibration_ack_with_firmware_reason_is_published(bridge: TanquesBridge, fake_mqtt: FakeMqttClient) -> None:
    """El rechazo del firmware por rango invalido (invalid_capacity) llega a tanques/ack con su motivo."""
    cmd = {"id": "cal-cap-bad", "cmd": "set_capacity", "tank": "a", "grams": 99999}
    bridge.handle_incoming_command(json.dumps(cmd))
    assert json.loads(bridge.command_queue.get_nowait()) == cmd

    bridge.process_device_line(json.dumps({"ack": "cal-cap-bad", "ok": False, "reason": "invalid_capacity"}))

    acks = [m for m in fake_mqtt.published_messages if m["topic"] == "tanques/ack"]
    assert acks[-1]["payload"] == {"ack": "cal-cap-bad", "ok": False, "reason": "invalid_capacity"}


def test_not_calibrated_rejection_ack_is_published(bridge: TanquesBridge, fake_mqtt: FakeMqttClient) -> None:
    """El rechazo del firmware con reason not_calibrated llega a tanques/ack sin alteraciones."""
    cmd = {"id": "c_nocal", "cmd": "set", "target": "pump", "value": True}
    bridge.handle_incoming_command(json.dumps(cmd))
    assert json.loads(bridge.command_queue.get_nowait()) == cmd

    bridge.process_device_line(json.dumps({"ack": "c_nocal", "ok": False, "reason": "not_calibrated"}))

    acks = [m for m in fake_mqtt.published_messages if m["topic"] == "tanques/ack"]
    assert acks[-1]["payload"] == {"ack": "c_nocal", "ok": False, "reason": "not_calibrated"}


# ==============================================================================
# Demo con Caudalímetro Real (--flow-serial): RealFlowReader
# ==============================================================================

class FakeFlowSerialPort:
    """Serial falso de solo lectura para probar RealFlowReader sin hardware."""

    def __init__(self, lines: Optional[List[str]] = None) -> None:
        self._lines: List[str] = list(lines or [])
        self.is_open = False
        self.dtr = True
        self.rts = True
        self.port: Optional[str] = None
        self.baudrate: Optional[int] = None
        self.timeout: Optional[float] = None

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def readline(self) -> bytes:
        if self._lines:
            return (self._lines.pop(0) + "\n").encode("utf-8")
        time.sleep(0.01)
        return b""


def _telemetry_line(flow_lpm: Any = 9.99) -> str:
    return json.dumps({
        "v": 1,
        "seq": 1,
        "uptime_ms": 100,
        "tank_a": {"weight_g": None, "level_pct": 10.0, "temp_c": 20.0},
        "tank_b": {"weight_g": None, "level_pct": 5.0, "temp_c": 20.0},
        "flow_lpm": flow_lpm,
        "actuators": {"pump": False},
        "alarms": {}
    })


def test_real_flow_reader_opens_read_only_without_writing() -> None:
    """RealFlowReader abre el puerto con DTR=False/RTS=False y nunca escribe (sin método write usado)."""
    fake_serial = FakeFlowSerialPort(['{"flow_lpm": 3.33}'])
    reader = RealFlowReader(port="COMX", serial_factory=lambda: fake_serial)
    reader.start()

    t0 = time.time()
    while time.time() - t0 < 2.0 and reader.get_flow_lpm() is None:
        time.sleep(0.02)

    assert fake_serial.dtr is False
    assert fake_serial.rts is False
    assert reader.get_flow_lpm() == pytest.approx(3.33)
    assert not hasattr(fake_serial, "write")  # el fake no define 'write': RealFlowReader nunca lo invoca

    reader.stop()


def test_real_flow_reader_ignores_non_json_lines() -> None:
    """Líneas que no son JSON (ruido de arranque) se ignoran sin crashear ni alterar el último valor."""
    fake_serial = FakeFlowSerialPort(['{"flow_lpm": 1.5}', "Arduino Uno Booting...", "{broken json:"])
    reader = RealFlowReader(port="COMX", serial_factory=lambda: fake_serial)
    reader.start()

    t0 = time.time()
    while time.time() - t0 < 2.0 and reader.get_flow_lpm() is None:
        time.sleep(0.02)

    assert reader.get_flow_lpm() == pytest.approx(1.5)
    reader.stop()


def test_flow_serial_replaces_simulated_flow_when_recent(fake_mqtt: FakeMqttClient) -> None:
    """1. Con --flow-serial activo y lectura reciente, el flow real reemplaza al simulado en Influx."""
    fake_serial = FakeFlowSerialPort(['{"flow_lpm": 3.33}'])
    reader = RealFlowReader(port="COMX", serial_factory=lambda: fake_serial)
    reader.start()

    t0 = time.time()
    while time.time() - t0 < 2.0 and reader.get_flow_lpm() is None:
        time.sleep(0.02)

    mock_influx = MagicMock()
    mock_influx.write_line_protocol.return_value = True
    b = TanquesBridge(influx_writer=mock_influx, mqtt_client=fake_mqtt, flow_reader=reader)

    b.process_device_line(_telemetry_line(flow_lpm=9.99))

    line_written = mock_influx.write_line_protocol.call_args[0][0]
    assert "flow_lpm=3.33" in line_written

    reader.stop()
    b.stop()


def test_flow_serial_stale_data_omits_field_and_warns_once(fake_mqtt: FakeMqttClient, caplog: pytest.LogCaptureFixture) -> None:
    """2. Con dato real viejo (> 3 s) o ausente, el campo flow_lpm no se escribe y se avisa una sola vez."""
    reader = RealFlowReader(port="COMX", max_age_s=3.0)
    reader._last_value = 1.23
    reader._last_time = time.time() - 10.0

    mock_influx = MagicMock()
    mock_influx.write_line_protocol.return_value = True
    b = TanquesBridge(influx_writer=mock_influx, mqtt_client=fake_mqtt, flow_reader=reader)

    with caplog.at_level(logging.WARNING, logger="edge-bridge"):
        b.process_device_line(_telemetry_line(flow_lpm=9.99))
        b.process_device_line(_telemetry_line(flow_lpm=9.99))

    assert mock_influx.write_line_protocol.call_count == 2
    for call in mock_influx.write_line_protocol.call_args_list:
        assert "flow_lpm" not in call[0][0]

    warnings = [r for r in caplog.records if "Caudal real" in r.message]
    assert len(warnings) == 1  # Aviso único, no repetido en cada trama

    b.stop()


def test_without_flow_serial_option_nothing_changes(fake_mqtt: FakeMqttClient) -> None:
    """3. Sin --flow-serial (flow_reader=None, default), el flow_lpm simulado se escribe sin alterar."""
    mock_influx = MagicMock()
    mock_influx.write_line_protocol.return_value = True
    b = TanquesBridge(influx_writer=mock_influx, mqtt_client=fake_mqtt)

    assert b.flow_reader is None
    b.process_device_line(_telemetry_line(flow_lpm=9.99))

    line_written = mock_influx.write_line_protocol.call_args[0][0]
    assert "flow_lpm=9.99" in line_written

    b.stop()


def test_flow_serial_requires_sim_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """--flow-serial (o FLOW_SERIAL_PORT) solo es válido junto con --source sim; otra fuente aborta."""
    import sys
    from edge.bridge import main

    monkeypatch.setattr(sys, "argv", ["bridge.py", "--source", "stdin", "--flow-serial", "COM4"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
