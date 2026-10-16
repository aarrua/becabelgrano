#!/usr/bin/env python3
"""
Simulador Físico de Tanques Interconectados (UTN FRSF / GITDA)
==============================================================
Modela dos tanques acoplados en serie con bomba de recirculación,
sensores virtuales con ruido, interlocks de seguridad y recepción
asíncrona de comandos por stdin.

Cumple estrictamente con el contrato de datos JSON del proyecto.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.yaml"


# ==============================================================================
# Modelos de Datos y Estado Físico
# ==============================================================================

@dataclass
class TankState:
    area_cm2: float
    height_max_cm: float
    volume_max_ml: float
    discharge_coeff: float
    volume_ml: float
    temp_c: float

    @property
    def level_pct(self) -> float:
        return min(100.0, max(0.0, (self.volume_ml / self.volume_max_ml) * 100.0))

    @property
    def height_cm(self) -> float:
        return self.volume_ml / self.area_cm2


@dataclass
class SimulatorState:
    tank_a: TankState
    tank_b: TankState
    pump_nominal_flow_lpm: float
    ambient_temp_c: float
    thermal_tau_s: float
    overflow_threshold_pct: float
    weight_noise_g: float
    flow_noise_lpm: float
    temp_noise_c: float

    # Variables de operación y estado
    actuators: Dict[str, bool] = field(default_factory=lambda: {"pump": False})
    alarms: Dict[str, bool] = field(default_factory=lambda: {
        "overflow_a": False,
        "overflow_b": False,
        "sensor_fault": False
    })
    mode: str = "auto"
    seq: int = 0
    start_time: float = field(default_factory=time.time)
    running: bool = True
    lock: threading.Lock = field(default_factory=threading.Lock)


# ==============================================================================
# Carga de Configuración
# ==============================================================================

DEFAULT_CONFIG: Dict[str, Any] = {
    "tank_a": {
        "area_cm2": 100.0,
        "height_max_cm": 40.0,
        "volume_max_ml": 4000.0,
        "discharge_coeff": 0.045,
        "initial_level_pct": 15.0,
        "initial_temp_c": 23.5,
    },
    "tank_b": {
        "area_cm2": 70.0,
        "height_max_cm": 35.0,
        "volume_max_ml": 2450.0,
        "discharge_coeff": 0.038,
        "initial_level_pct": 10.0,
        "initial_temp_c": 23.2,
    },
    "pump": {
        "nominal_flow_lpm": 2.2,
        "initial_state": False,
        "initial_pump": False,
    },
    "thermal": {
        "ambient_temp_c": 22.5,
        "tau_seconds": 300.0,
    },
    "interlocks": {
        "overflow_threshold_pct": 85.0,
    },
    "noise": {
        "weight_noise_g": 1.2,
        "flow_noise_lpm": 0.04,
        "temp_noise_c": 0.08,
    },
    "timing": {
        "sample_interval_s": 1.0,
    },
}


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    """Parseador básico de YAML por indentación para no depender estrictamente de PyYAML."""
    res: Dict[str, Any] = {}
    current_section: Optional[str] = None
    for raw_line in text.splitlines():
        line = raw_line.split("#")[0].rstrip()
        if not line:
            continue
        if not line.startswith(" ") and ":" in line:
            sec_name = line.split(":")[0].strip()
            current_section = sec_name
            res[current_section] = {}
        elif line.startswith("  ") and ":" in line and current_section:
            parts = line.strip().split(":", 1)
            k = parts[0].strip()
            raw_val = parts[1].strip()
            val: Any = raw_val
            if raw_val.lower() == "true":
                val = True
            elif raw_val.lower() == "false":
                val = False
            else:
                try:
                    val = float(raw_val) if "." in raw_val else int(raw_val)
                except ValueError:
                    val = raw_val.strip("\"'")
            res[current_section][k] = val
    return res


def load_config(config_path: Optional[Union[Path, str]]) -> Dict[str, Any]:
    """Carga configuración desde YAML si existe o usa default."""
    if config_path and config_path.is_file():
        try:
            import yaml  # type: ignore
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
        except ImportError:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = _parse_simple_yaml(f.read())
        except Exception as e:
            sys.stderr.write(f"[WARN] Error leyendo {config_path}: {e}. Usando configuración base.\n")
            loaded = None

        if isinstance(loaded, dict):
            cfg = DEFAULT_CONFIG.copy()
            for k, v in loaded.items():
                if isinstance(v, dict) and k in cfg:
                    cfg[k].update(v)
                else:
                    cfg[k] = v
            return cfg
    return DEFAULT_CONFIG


# ==============================================================================
# Lógica Física de Simulación
# ==============================================================================

def step_physics(state: SimulatorState, dt: float) -> float:
    """
    Avanza la física del sistema dt segundos.
    Retorna el caudal instantáneo real impulsado por la bomba (L/min).
    """
    with state.lock:
        pump_on = state.actuators.get("pump", False)
        
        # 1. Caudal de entrada a Tanque A (de la bomba)
        flow_lpm = state.pump_nominal_flow_lpm if pump_on else 0.0
        # Convertir L/min a ml/s (1 L/min = 1000 ml / 60 s = 16.6667 ml/s)
        q_in_a_ml_s = (flow_lpm * 1000.0) / 60.0

        # 2. Caudal de salida Tanque A -> Tanque B (Torricelli simplificado)
        # q_out = c_d * A_out * sqrt(2 * g * h) -> aproximado por constante * sqrt(h)
        h_a = state.tank_a.height_cm
        if h_a > 0.05:
            # ml/s de descarga de A
            q_out_a_ml_s = state.tank_a.discharge_coeff * state.tank_a.area_cm2 * math.sqrt(2.0 * 981.0 * h_a) * 0.02
        else:
            q_out_a_ml_s = 0.0

        # 3. Caudal de salida Tanque B -> Reservorio
        h_b = state.tank_b.height_cm
        if h_b > 0.05:
            q_out_b_ml_s = state.tank_b.discharge_coeff * state.tank_b.area_cm2 * math.sqrt(2.0 * 981.0 * h_b) * 0.02
        else:
            q_out_b_ml_s = 0.0

        # Integración de volúmenes (Euler explícito)
        delta_v_a = (q_in_a_ml_s - q_out_a_ml_s) * dt
        delta_v_b = (q_out_a_ml_s - q_out_b_ml_s) * dt

        state.tank_a.volume_ml = max(0.0, min(state.tank_a.volume_max_ml * 1.05, state.tank_a.volume_ml + delta_v_a))
        state.tank_b.volume_ml = max(0.0, min(state.tank_b.volume_max_ml * 1.05, state.tank_b.volume_ml + delta_v_b))

        # 4. Dinámica Térmica (pasiva hacia ambiente, ley de enfriamiento de Newton)
        decay = math.exp(-dt / state.thermal_tau_s)
        state.tank_a.temp_c = state.ambient_temp_c + (state.tank_a.temp_c - state.ambient_temp_c) * decay
        state.tank_b.temp_c = state.ambient_temp_c + (state.tank_b.temp_c - state.ambient_temp_c) * decay

        # 5. Evaluación de Interlocks de Seguridad (Corte de Bomba automático)
        pct_a = state.tank_a.level_pct
        pct_b = state.tank_b.level_pct

        overflow_a = pct_a >= state.overflow_threshold_pct
        overflow_b = pct_b >= state.overflow_threshold_pct

        state.alarms["overflow_a"] = overflow_a
        state.alarms["overflow_b"] = overflow_b

        # Si hay sobrellenado en cualquiera de los tanques, corte obligatorio
        if (overflow_a or overflow_b) and state.actuators.get("pump", False):
            state.actuators["pump"] = False
            sys.stderr.write(
                f"[INTERLOCK TRIGGERED] Bomba apagada de emergencia! "
                f"Nivel A: {pct_a:.1f}%, Nivel B: {pct_b:.1f}%\n"
            )
            sys.stderr.flush()

        return flow_lpm


# ==============================================================================
# Construcción de Telemetría (Contrato JSON)
# ==============================================================================

def build_telemetry_frame(state: SimulatorState, flow_actual_lpm: float) -> Dict[str, Any]:
    """Genera la trama JSON correspondiente al contrato con ruido instrumental."""
    with state.lock:
        state.seq += 1
        uptime_ms = int((time.time() - state.start_time) * 1000)

        # Densidad agua = 1.0 g/ml -> peso = volumen_ml + ruido
        noise_w_a = random.gauss(0.0, state.weight_noise_g)
        noise_w_b = random.gauss(0.0, state.weight_noise_g)
        weight_a = max(0.0, round(state.tank_a.volume_ml + noise_w_a, 1))
        weight_b = max(0.0, round(state.tank_b.volume_ml + noise_w_b, 1))

        # Ruido térmico
        noise_t_a = random.gauss(0.0, state.temp_noise_c)
        noise_t_b = random.gauss(0.0, state.temp_noise_c)
        temp_a = round(state.tank_a.temp_c + noise_t_a, 1)
        temp_b = round(state.tank_b.temp_c + noise_t_b, 1)

        # Ruido caudal
        if flow_actual_lpm > 0.05:
            flow_noisy = max(0.0, round(flow_actual_lpm + random.gauss(0.0, state.flow_noise_lpm), 2))
        else:
            flow_noisy = 0.0

        level_a = round(state.tank_a.level_pct, 1)
        level_b = round(state.tank_b.level_pct, 1)

        frame = {
            "v": 1,
            "seq": state.seq,
            "uptime_ms": uptime_ms,
            "tank_a": {
                "weight_g": weight_a,
                "level_pct": level_a,
                "temp_c": temp_a
            },
            "tank_b": {
                "weight_g": weight_b,
                "level_pct": level_b,
                "temp_c": temp_b
            },
            "flow_lpm": flow_noisy,
            "actuators": dict(state.actuators),
            "alarms": dict(state.alarms),
            "mode": state.mode
        }
        return frame


# ==============================================================================
# Hilo Receptor de Comandos (stdin)
# ==============================================================================

VALID_TARGETS = {"pump"}


def process_command(state: SimulatorState, line: str) -> None:
    """Procesa un comando JSON recibido y emite su respuesta ack."""
    line = line.strip()
    if not line:
        return

    try:
        cmd_obj = json.loads(line)
    except json.JSONDecodeError:
        resp = {"ack": "unknown", "ok": False, "reason": "invalid_json"}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()
        return

    cmd_id = cmd_obj.get("id", "none")
    cmd_action = cmd_obj.get("cmd")
    target = cmd_obj.get("target")
    value = cmd_obj.get("value")

    if cmd_action != "set":
        resp = {"ack": cmd_id, "ok": False, "reason": "unsupported_cmd"}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()
        return

    if target not in VALID_TARGETS:
        resp = {"ack": cmd_id, "ok": False, "reason": "unknown_target"}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()
        return

    if not isinstance(value, bool):
        resp = {"ack": cmd_id, "ok": False, "reason": "invalid_value_type"}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()
        return

    with state.lock:
        # Validación de interlocks ante encendido de bomba
        if target == "pump" and value is True:
            if state.alarms.get("overflow_a", False):
                resp = {"ack": cmd_id, "ok": False, "reason": "overflow_a"}
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
                return
            if state.alarms.get("overflow_b", False):
                resp = {"ack": cmd_id, "ok": False, "reason": "overflow_b"}
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
                return

        # Aplicar cambio
        state.actuators[target] = value
        resp = {"ack": cmd_id, "ok": True}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


def stdin_listener(state: SimulatorState) -> None:
    """Lee comandos línea a línea desde standard input."""
    while state.running:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            process_command(state, line)
        except Exception as e:
            sys.stderr.write(f"[ERROR stdin_listener] {e}\n")
            sys.stderr.flush()
            break


# ==============================================================================
# Bucle Principal de Ejecución
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador Didáctico de Tanques (UTN FRSF)")
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG_PATH), help="Ruta al archivo config.yaml")
    parser.add_argument("--speed", type=float, default=1.0, help="Multiplicador de velocidad de simulación (ej: 5.0)")
    parser.add_argument("--interval", type=float, default=1.0, help="Intervalo real de emisión en segundos (default 1.0)")
    parser.add_argument("--pump-on", action="store_true", help="Inicia la simulación con la bomba encendida")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))

    t_a_cfg = cfg["tank_a"]
    t_b_cfg = cfg["tank_b"]
    p_cfg = cfg["pump"]
    th_cfg = cfg["thermal"]
    int_cfg = cfg["interlocks"]
    noise_cfg = cfg["noise"]

    # Inicializar volúmenes según porcentaje inicial
    init_vol_a = (t_a_cfg["initial_level_pct"] / 100.0) * t_a_cfg["volume_max_ml"]
    init_vol_b = (t_b_cfg["initial_level_pct"] / 100.0) * t_b_cfg["volume_max_ml"]

    tank_a = TankState(
        area_cm2=float(t_a_cfg["area_cm2"]),
        height_max_cm=float(t_a_cfg["height_max_cm"]),
        volume_max_ml=float(t_a_cfg["volume_max_ml"]),
        discharge_coeff=float(t_a_cfg["discharge_coeff"]),
        volume_ml=init_vol_a,
        temp_c=float(t_a_cfg["initial_temp_c"]),
    )

    tank_b = TankState(
        area_cm2=float(t_b_cfg["area_cm2"]),
        height_max_cm=float(t_b_cfg["height_max_cm"]),
        volume_max_ml=float(t_b_cfg["volume_max_ml"]),
        discharge_coeff=float(t_b_cfg["discharge_coeff"]),
        volume_ml=init_vol_b,
        temp_c=float(t_b_cfg["initial_temp_c"]),
    )

    initial_pump = bool(args.pump_on or p_cfg.get("initial_pump", False) or p_cfg.get("initial_state", False))

    state = SimulatorState(
        tank_a=tank_a,
        tank_b=tank_b,
        pump_nominal_flow_lpm=float(p_cfg["nominal_flow_lpm"]),
        ambient_temp_c=float(th_cfg["ambient_temp_c"]),
        thermal_tau_s=float(th_cfg["tau_seconds"]),
        overflow_threshold_pct=float(int_cfg["overflow_threshold_pct"]),
        weight_noise_g=float(noise_cfg["weight_noise_g"]),
        flow_noise_lpm=float(noise_cfg["flow_noise_lpm"]),
        temp_noise_c=float(noise_cfg["temp_noise_c"]),
        actuators={"pump": initial_pump},
    )

    # Iniciar hilo para comandos stdin
    listener_thread = threading.Thread(target=stdin_listener, args=(state,), daemon=True)
    listener_thread.start()

    sys.stderr.write(
        f"[INFO] Simulador de tanques iniciado. Intervalo: {args.interval}s, "
        f"Velocidad: {args.speed}x (dt={args.interval * args.speed}s), Bomba: {initial_pump}\n"
    )
    sys.stderr.flush()

    try:
        while state.running:
            dt_sim = args.interval * args.speed
            flow_actual = step_physics(state, dt=dt_sim)
            frame = build_telemetry_frame(state, flow_actual)

            # Emitir trama JSON por stdout (1 línea limpia)
            sys.stdout.write(json.dumps(frame) + "\n")
            sys.stdout.flush()

            time.sleep(args.interval)
    except KeyboardInterrupt:
        state.running = False
        sys.stderr.write("[INFO] Simulador detenido limpiamente por usuario.\n")


if __name__ == "__main__":
    main()
