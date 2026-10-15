#!/usr/bin/env python3
"""
Pruebas Automatizadas de Validación para edge/simulator.py y edge/bridge.py (Fase 1)
"""

import json
import time
import unittest
from edge.bridge import format_influx_line, InfluxWriter
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


if __name__ == "__main__":
    unittest.main()
