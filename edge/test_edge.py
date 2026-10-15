#!/usr/bin/env python3
"""
Pruebas Automatizadas de Validación para edge/simulator.py y edge/bridge.py (Fase 1)
"""

import json
from pathlib import Path
import time
import unittest
from unittest.mock import MagicMock, patch
from edge.bridge import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_SIM_PATH,
    InfluxWriter,
    format_influx_line,
    logger as bridge_logger,
    run_bridge,
    stream_simulator,
)
from edge.simulator import (
    SimulatorState,
    TankState,
    build_telemetry_frame,
    process_command,
    step_physics
)


class TestSimulatorPhysics(unittest.TestCase):
    def setUp(self):
        self.tank_a = TankState(
            area_cm2=100.0,
            height_max_cm=40.0,
            volume_max_ml=4000.0,
            discharge_coeff=0.045,
            volume_ml=1000.0,
            temp_c=25.0
        )
        self.tank_b = TankState(
            area_cm2=70.0,
            height_max_cm=35.0,
            volume_max_ml=2450.0,
            discharge_coeff=0.038,
            volume_ml=500.0,
            temp_c=24.0
        )
        self.state = SimulatorState(
            tank_a=self.tank_a,
            tank_b=self.tank_b,
            pump_nominal_flow_lpm=2.2,
            ambient_temp_c=22.0,
            thermal_tau_s=300.0,
            overflow_threshold_pct=95.0,
            weight_noise_g=0.0,
            flow_noise_lpm=0.0,
            temp_noise_c=0.0,
            actuators={"pump": True}
        )

    def test_physics_filling_and_discharge(self):
        vol_a_init = self.state.tank_a.volume_ml
        # Avanzar 5 segundos con bomba encendida
        step_physics(self.state, dt=5.0)
        # Tanque A debe haber recibido líquido de la bomba
        self.assertGreater(self.state.tank_a.volume_ml, vol_a_init)
        # Tanque B debe haber recibido descarga del Tanque A
        self.assertGreater(self.state.tank_b.volume_ml, 500.0)

    def test_interlock_shuts_off_pump_on_overflow(self):
        # Forzar volumen de Tanque A al 96%
        self.state.tank_a.volume_ml = self.state.tank_a.volume_max_ml * 0.96
        self.state.actuators["pump"] = True
        step_physics(self.state, dt=1.0)

        # La bomba debe haberse apagado automáticamente
        self.assertFalse(self.state.actuators["pump"])
        self.assertTrue(self.state.alarms["overflow_a"])

    def test_interlock_rejects_pump_command_when_overflow_active(self):
        self.state.alarms["overflow_a"] = True
        self.state.actuators["pump"] = False

        # Intentar prender bomba con overflow activo
        # Simular process_command
        import sys, io
        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            process_command(self.state, json.dumps({
                "id": "cmd_test_1",
                "cmd": "set",
                "target": "pump",
                "value": True
            }))
        finally:
            sys.stdout = old_stdout

        resp = json.loads(captured.getvalue().strip())
        self.assertEqual(resp["ack"], "cmd_test_1")
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["reason"], "overflow_a")
        self.assertFalse(self.state.actuators["pump"])


class TestBridgeFormatting(unittest.TestCase):
    def test_format_influx_line(self):
        payload = {
            "v": 1,
            "seq": 42,
            "uptime_ms": 12000,
            "tank_a": {"weight_g": 1250.5, "level_pct": 31.2, "temp_c": 23.4},
            "tank_b": {"weight_g": 620.0, "level_pct": 25.3, "temp_c": 23.1},
            "flow_lpm": 2.15,
            "actuators": {"pump": True},
            "alarms": {"overflow_a": False, "overflow_b": False, "sensor_fault": False},
            "mode": "auto"
        }
        ts_ns = 1728950000000000000
        line = format_influx_line(payload, ts_ns)
        self.assertIsNotNone(line)
        self.assertTrue(line.startswith("telemetry,mode=auto "))
        self.assertIn("seq=42i", line)
        self.assertIn("tank_a_level_pct=31.20", line)
        self.assertIn("pump=true", line)
        self.assertIn("overflow_a=false", line)
        self.assertTrue(line.endswith(f" {ts_ns}"))


class TestBridgeResilienceAndLogging(unittest.TestCase):
    def test_default_paths_exist(self):
        self.assertTrue(DEFAULT_SIM_PATH.is_file(), f"No existe {DEFAULT_SIM_PATH}")
        self.assertTrue(DEFAULT_CONFIG_PATH.is_file(), f"No existe {DEFAULT_CONFIG_PATH}")
        self.assertEqual(DEFAULT_SIM_PATH.name, "simulator.py")
        self.assertEqual(DEFAULT_CONFIG_PATH.name, "config.yaml")

    def test_stream_simulator_logs_failure_and_retries(self):
        import os
        import tempfile

        class StopRetry(Exception):
            pass

        # Script temporal que falla con código 42 y stderr
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write("import sys\nsys.stderr.write('CRASH_ERR_SIM_FAIL\\n')\nsys.exit(42)\n")
            fpath = tf.name

        try:
            with patch("edge.bridge.time.sleep", side_effect=StopRetry), \
                 patch.object(bridge_logger, "error") as mock_log_err:
                gen = stream_simulator(sim_script=fpath, config_path=None, initial_backoff=0.01)
                with self.assertRaises(StopRetry):
                    next(gen)

                mock_log_err.assert_called()
                error_call_str = " ".join(str(arg) for arg in mock_log_err.call_args[0])
                self.assertIn("42", error_call_str)
                self.assertIn("CRASH_ERR_SIM_FAIL", error_call_str)
        finally:
            try:
                os.remove(fpath)
            except Exception:
                pass

    def test_run_bridge_logs_every_n_successful_writes(self):
        sample_frame = json.dumps({
            "v": 1,
            "seq": 1,
            "uptime_ms": 1000,
            "tank_a": {"weight_g": 1000.0, "level_pct": 25.0, "temp_c": 22.0},
            "tank_b": {"weight_g": 500.0, "level_pct": 20.0, "temp_c": 22.0},
            "flow_lpm": 1.5,
            "actuators": {"pump": True},
            "alarms": {"overflow_a": False, "overflow_b": False, "sensor_fault": False},
            "mode": "auto"
        })

        def mock_lines():
            for _ in range(65):
                yield sample_frame

        mock_influx = MagicMock(spec=InfluxWriter)
        mock_influx.org = "test-org"
        mock_influx.bucket = "test-bucket"
        mock_influx.write_line_protocol.return_value = True

        with patch("edge.bridge.stream_stdin", return_value=mock_lines()), \
             patch.object(bridge_logger, "info") as mock_info:
            run_bridge("stdin", mock_influx, log_interval=30)

        # Se enviaron 65 tramas con log_interval=30.
        # Debe haber logueado a nivel INFO en 30 y 60.
        summary_logs = [
            call for call in mock_info.call_args_list
            if "escrituras exitosas acumuladas" in str(call)
        ]
        self.assertEqual(len(summary_logs), 2)

    def test_simulator_initial_pump_from_config(self):
        from edge.simulator import load_config
        import tempfile
        import os

        yaml_content = """
tank_a:
  area_cm2: 100.0
  height_max_cm: 40.0
  volume_max_ml: 4000.0
  discharge_coeff: 0.045
  initial_level_pct: 15.0
  initial_temp_c: 23.5
tank_b:
  area_cm2: 70.0
  height_max_cm: 35.0
  volume_max_ml: 2450.0
  discharge_coeff: 0.038
  initial_level_pct: 10.0
  initial_temp_c: 23.2
pump:
  nominal_flow_lpm: 2.2
  initial_pump: true
"""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tf:
            tf.write(yaml_content)
            cfg_path = tf.name

        try:
            cfg = load_config(Path(cfg_path))
            self.assertTrue(cfg["pump"].get("initial_pump"))
        finally:
            try:
                os.remove(cfg_path)
            except Exception:
                pass

    def test_bridge_passes_pump_on_flag(self):
        mock_influx = MagicMock(spec=InfluxWriter)
        mock_influx.org = "test-org"
        mock_influx.bucket = "test-bucket"

        with patch("edge.bridge.stream_simulator", return_value=iter([])) as mock_sim:
            run_bridge("sim", mock_influx, pump_on=True)
            mock_sim.assert_called_once()
            _, kwargs = mock_sim.call_args
            self.assertTrue(kwargs.get("pump_on"))
            self.assertIn("--pump-on", kwargs.get("extra_args", []))


if __name__ == "__main__":
    unittest.main()
