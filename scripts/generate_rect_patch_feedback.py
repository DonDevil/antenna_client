#!/usr/bin/env python3
"""Generate raw CST-backed feedback rows for rectangular microstrip patch ANN training.

This script is intentionally server-independent. It samples valid target specifications,
builds a deterministic rectangular patch recipe, applies bounded perturbations to the
ANN-relevant geometry fields, runs CST directly, extracts S11/far-field metrics, and
appends rows to data/raw/rect_patch_feedback_v1.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import signal
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SHUTDOWN = threading.Event()
_SIGINT_COUNT = 0
_ACTIVE_CST: CSTApp | None = None


def _disconnect_cst_worker(cst: CSTApp) -> None:
    try:
        cst.disconnect()
    except Exception:
        pass


def _sigint_handler(signum: int, frame: object) -> None:  # noqa: ARG001
    global _SIGINT_COUNT
    _SIGINT_COUNT += 1

    if _SIGINT_COUNT == 1:
        print("\n[Ctrl+C] Shutdown requested. Stopping after the current CST call returns.", flush=True)
        if _ACTIVE_CST is not None:
            threading.Thread(target=_disconnect_cst_worker, args=(_ACTIVE_CST,), daemon=True).start()
    else:
        print("\n[Ctrl+C] Forced exit requested. Terminating immediately.", flush=True)
        os._exit(130)
    _SHUTDOWN.set()


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cst_client.cst_app import CSTApp
from executor.vba_generator import VBAGenerator
from utils.logger import get_logger


logger = get_logger(__name__)

RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "rect_patch_feedback_v1.csv"

CSV_COLUMNS = [
    "run_id",
    "timestamp_utc",
    "antenna_family",
    "patch_shape",
    "feed_type",
    "polarization",
    "substrate_name",
    "conductor_name",
    "target_frequency_ghz",
    "target_bandwidth_mhz",
    "target_minimum_gain_dbi",
    "target_maximum_vswr",
    "target_minimum_return_loss_db",
    "substrate_epsilon_r",
    "substrate_height_mm",
    "patch_length_mm",
    "patch_width_mm",
    "patch_height_mm",
    "substrate_length_mm",
    "substrate_width_mm",
    "feed_length_mm",
    "feed_width_mm",
    "feed_offset_x_mm",
    "feed_offset_y_mm",
    "actual_center_frequency_ghz",
    "actual_bandwidth_mhz",
    "actual_return_loss_db",
    "actual_vswr",
    "actual_gain_dbi",
    "actual_radiation_efficiency_pct",
    "actual_total_efficiency_pct",
    "actual_directivity_dbi",
    "actual_peak_theta_deg",
    "actual_peak_phi_deg",
    "actual_front_to_back_db",
    "actual_axial_ratio_db",
    "accepted",
    "solver_status",
    "simulation_time_sec",
    "notes",
    "farfield_artifact_path",
    "s11_artifact_path",
]

SUBSTRATE_LIBRARY = [
    {"name": "Rogers RT/duroid 5880", "epsilon_r": 2.2, "loss_tangent": 0.0009},
    {"name": "Rogers RO4350B", "epsilon_r": 3.48, "loss_tangent": 0.0037},
    {"name": "Rogers RO3003", "epsilon_r": 3.0, "loss_tangent": 0.0013},
    {"name": "Isola Astra MT77", "epsilon_r": 3.0, "loss_tangent": 0.0017},
    {"name": "FR4", "epsilon_r": 4.4, "loss_tangent": 0.02},
]

CONDUCTOR_LIBRARY = [
    {"name": "Copper (annealed)", "conductivity_s_per_m": 5.8e7},
    {"name": "Aluminum", "conductivity_s_per_m": 3.56e7},
    {"name": "Silver", "conductivity_s_per_m": 6.3e7},
]

SAFE_BOUNDS = {
    "target_frequency_ghz": (2.0, 7.0),
    "target_bandwidth_mhz": (30.0, 300.0),
    "substrate_epsilon_r": (2.2, 4.4),
    "substrate_height_mm": (0.8, 3.2),
    "patch_length_mm": (5.0, 80.0),
    "patch_width_mm": (5.0, 100.0),
    "feed_width_mm": (0.5, 8.0),
    "feed_offset_y_mm": (-50.0, 0.0),
}

C0 = 299_792_458.0


@dataclass
class SampleInput:
    substrate_name: str
    substrate_epsilon_r: float
    substrate_loss_tangent: float
    conductor_name: str
    conductor_conductivity_s_per_m: float
    substrate_height_mm: float
    target_frequency_ghz: float
    target_bandwidth_mhz: float
    target_minimum_gain_dbi: float
    target_maximum_vswr: float
    target_minimum_return_loss_db: float


@dataclass
class PatchGeometry:
    patch_length_mm: float
    patch_width_mm: float
    patch_height_mm: float
    substrate_length_mm: float
    substrate_width_mm: float
    feed_length_mm: float
    feed_width_mm: float
    feed_offset_x_mm: float
    feed_offset_y_mm: float


PARAM_DEFAULTS = {
    "sub_w": 40.0,
    "sub_l": 50.0,
    "sub_h": 1.6,
    "patch_w": 24.0,
    "patch_l": 20.0,
    "patch_h": 0.035,
    "feed_w": 2.0,
    "feed_x": 0.0,
    "freq_start_ghz": 2.0,
    "freq_stop_ghz": 3.0,
    "ff_freq_ghz": 2.4,
    "er_sub": 2.2,
    "tan_delta_sub": 0.001,
    "sigma_cond": 5.8e7,
}


def _clamp(value: float, bounds: tuple[float, float]) -> float:
    return max(bounds[0], min(bounds[1], value))


def _round(value: float | None, digits: int = 6) -> str:
    if value is None:
        return ""
    return f"{float(value):.{digits}f}"


def _to_bool_text(value: bool) -> str:
    return "true" if value else "false"


def _db_to_percent(value: float | None) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if 0.0 <= numeric <= 100.0:
        return numeric
    return (10.0 ** (numeric / 10.0)) * 100.0


def _return_loss_to_vswr(return_loss_db: float | None) -> float | None:
    if return_loss_db is None:
        return None
    rl = abs(float(return_loss_db))
    gamma = 10.0 ** (-rl / 20.0)
    if gamma >= 1.0:
        return None
    return (1.0 + gamma) / (1.0 - gamma)


def _sample_input(rng: random.Random) -> SampleInput:
    substrate = rng.choice(SUBSTRATE_LIBRARY)
    conductor = rng.choice(CONDUCTOR_LIBRARY)
    return SampleInput(
        substrate_name=str(substrate["name"]),
        substrate_epsilon_r=float(substrate["epsilon_r"]),
        substrate_loss_tangent=float(substrate["loss_tangent"]),
        conductor_name=str(conductor["name"]),
        conductor_conductivity_s_per_m=float(conductor["conductivity_s_per_m"]),
        substrate_height_mm=round(rng.uniform(0.8, 3.2), 3),
        target_frequency_ghz=round(rng.uniform(2.0, 7.0), 4),
        target_bandwidth_mhz=round(rng.uniform(30.0, 300.0), 3),
        target_minimum_gain_dbi=round(rng.uniform(2.0, 9.0), 3),
        target_maximum_vswr=round(rng.uniform(1.5, 2.5), 3),
        target_minimum_return_loss_db=round(rng.uniform(10.0, 20.0), 3),
    )


def _microstrip_50ohm_width_mm(substrate_height_mm: float, epsilon_r: float) -> float:
    """Hammerstad 50-ohm microstrip trace width (Wheeler/Schneider synthesis)."""
    h = max(substrate_height_mm, 0.1)
    er = max(epsilon_r, 1.1)
    # Narrow-trace trial (W/H < 2): A-parameter form
    A = (50.0 / 60.0) * math.sqrt((er + 1.0) / 2.0) + ((er - 1.0) / (er + 1.0)) * (0.23 + 0.11 / er)
    w_h = (8.0 * math.exp(A)) / (math.exp(2.0 * A) - 2.0)
    if w_h > 2.0:
        # Wide-trace case (W/H >= 2): B-parameter form
        B = (377.0 * math.pi) / (2.0 * 50.0 * math.sqrt(er))
        w_h = (2.0 / math.pi) * (
            B
            - 1.0
            - math.log(2.0 * B - 1.0)
            + ((er - 1.0) / (2.0 * er)) * (math.log(B - 1.0) + 0.39 - 0.61 / er)
        )
    return max(0.5, min(8.0, w_h * h))


def _baseline_geometry(sample: SampleInput) -> PatchGeometry:
    freq_hz = sample.target_frequency_ghz * 1e9
    er = sample.substrate_epsilon_r
    h_m = sample.substrate_height_mm / 1000.0

    width_m = (C0 / (2.0 * freq_hz)) * math.sqrt(2.0 / (er + 1.0))
    eps_eff = ((er + 1.0) / 2.0) + ((er - 1.0) / 2.0) * (1.0 / math.sqrt(1.0 + 12.0 * h_m / width_m))
    delta_l = 0.412 * h_m * ((eps_eff + 0.3) * (width_m / h_m + 0.264)) / ((eps_eff - 0.258) * (width_m / h_m + 0.8))
    effective_length_m = C0 / (2.0 * freq_hz * math.sqrt(eps_eff))
    length_m = effective_length_m - 2.0 * delta_l

    patch_length_mm = _clamp(length_m * 1000.0, SAFE_BOUNDS["patch_length_mm"])
    patch_width_mm = _clamp(width_m * 1000.0, SAFE_BOUNDS["patch_width_mm"])
    feed_width_mm = _clamp(
        _microstrip_50ohm_width_mm(sample.substrate_height_mm, sample.substrate_epsilon_r),
        SAFE_BOUNDS["feed_width_mm"],
    )
    feed_offset_y_mm = -patch_length_mm / 2.0
    substrate_length_mm = max(patch_length_mm + 12.0 * sample.substrate_height_mm, patch_length_mm + 20.0)
    substrate_width_mm = max(patch_width_mm + 12.0 * sample.substrate_height_mm, patch_width_mm + 20.0)
    feed_length_mm = max(0.5, substrate_length_mm / 2.0 - patch_length_mm / 2.0)

    return PatchGeometry(
        patch_length_mm=patch_length_mm,
        patch_width_mm=patch_width_mm,
        patch_height_mm=0.035,
        substrate_length_mm=substrate_length_mm,
        substrate_width_mm=substrate_width_mm,
        feed_length_mm=feed_length_mm,
        feed_width_mm=feed_width_mm,
        feed_offset_x_mm=0.0,
        feed_offset_y_mm=feed_offset_y_mm,
    )


def _perturb_geometry(base: PatchGeometry, rng: random.Random) -> PatchGeometry:
    patch_length_mm = _clamp(base.patch_length_mm * rng.uniform(0.85, 1.15), SAFE_BOUNDS["patch_length_mm"])
    patch_width_mm = _clamp(base.patch_width_mm * rng.uniform(0.85, 1.15), SAFE_BOUNDS["patch_width_mm"])
    feed_width_mm = _clamp(base.feed_width_mm * rng.uniform(0.8, 1.2), SAFE_BOUNDS["feed_width_mm"])
    feed_offset_y_mm = -patch_length_mm / 2.0

    substrate_length_mm = max(base.substrate_length_mm, patch_length_mm + 20.0)
    substrate_width_mm = max(base.substrate_width_mm, patch_width_mm + 20.0)
    feed_length_mm = max(0.5, substrate_length_mm / 2.0 - patch_length_mm / 2.0)

    return PatchGeometry(
        patch_length_mm=patch_length_mm,
        patch_width_mm=patch_width_mm,
        patch_height_mm=base.patch_height_mm,
        substrate_length_mm=substrate_length_mm,
        substrate_width_mm=substrate_width_mm,
        feed_length_mm=feed_length_mm,
        feed_width_mm=feed_width_mm,
        feed_offset_x_mm=base.feed_offset_x_mm,
        feed_offset_y_mm=feed_offset_y_mm,
    )


def _accepted(row: dict[str, Any]) -> bool:
    return (
        row["antenna_family"] == "microstrip_patch"
        and row["patch_shape"] == "rectangular"
        and row["feed_type"] == "edge"
        and float(row["target_frequency_ghz"] or 0.0) > 0.0
        and float(row["target_bandwidth_mhz"] or 0.0) > 0.0
        and float(row["actual_center_frequency_ghz"] or 0.0) > 0.0
        and float(row["actual_bandwidth_mhz"] or 0.0) > 0.0
        and float(row["actual_vswr"] or 0.0) > 0.0
        and float(row["patch_length_mm"] or 0.0) > 0.0
        and float(row["patch_width_mm"] or 0.0) > 0.0
        and float(row["feed_width_mm"] or 0.0) > 0.0
        and float(row["substrate_height_mm"] or 0.0) > 0.0
        and row["solver_status"] == "success"
    )


def _append_csv_row(row: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not output_path.exists()
    with output_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        if needs_header:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in CSV_COLUMNS})


def _apply_macro(cst: CSTApp, generator: VBAGenerator, command: str, params: dict[str, Any]) -> None:
    macro = generator.generate_macro(command, params)
    if not cst.execute_macro(macro, title=command):
        raise RuntimeError(f"CST macro failed: {command}")


def _build_model(
    cst: CSTApp,
    generator: VBAGenerator,
    project_name: str,
) -> None:
    if not cst.create_project(project_name):
        raise RuntimeError("Failed to create CST project")

    _apply_macro(cst, generator, "set_units", {"geometry": "mm", "frequency": "GHz"})

    for param_name, default_value in PARAM_DEFAULTS.items():
        if not cst.set_parameter(param_name, default_value, create_only=True):
            raise RuntimeError(f"Failed to define CST parameter: {param_name}")

    _apply_macro(cst, generator, "set_frequency_range", {
        "start_ghz": "freq_start_ghz",
        "stop_ghz": "freq_stop_ghz",
    })

    _apply_macro(cst, generator, "define_material", {
        "name": "dataset_substrate",
        "kind": "dielectric",
        "epsilon_r": "er_sub",
        "loss_tangent": "tan_delta_sub",
    })
    _apply_macro(cst, generator, "define_material", {
        "name": "dataset_conductor",
        "kind": "conductor",
        "conductivity_s_per_m": "sigma_cond",
    })
    _apply_macro(cst, generator, "create_component", {"component": "antenna"})

    _apply_macro(cst, generator, "create_substrate", {
        "component": "antenna",
        "name": "substrate",
        "material": "dataset_substrate",
        "origin_mm": {"x": 0.0, "y": 0.0, "z": 0.0},
        "width_mm": "sub_w",
        "length_mm": "sub_l",
        "height_mm": "sub_h",
    })
    _apply_macro(cst, generator, "create_ground_plane", {
        "component": "antenna",
        "name": "ground",
        "material": "dataset_conductor",
        "width_mm": "sub_w",
        "length_mm": "sub_l",
        "z_mm": 0.0,
        "thickness_mm": "patch_h",
    })

    _apply_macro(cst, generator, "create_patch", {
        "component": "antenna",
        "name": "patch",
        "material": "dataset_conductor",
        "center_mm": {"x": 0.0, "y": 0.0, "z": "sub_h"},
        "width_mm": "patch_w",
        "length_mm": "patch_l",
        "thickness_mm": "patch_h",
    })

    # start_mm = substrate edge (lower y = more negative) so that Yrange is passed
    # as (lower, upper) = ("-sub_l/2", "-patch_l/2") — this is required because
    # _create_feedline passes start["y"] as y_min when values are parameter expressions.
    _apply_macro(cst, generator, "create_feedline", {
        "component": "antenna",
        "name": "feedline",
        "material": "dataset_conductor",
        "start_mm": {"x": "feed_x", "y": "-sub_l/2", "z": "sub_h"},
        "end_mm": {"x": "feed_x", "y": "-patch_l/2", "z": "sub_h"},
        "width_mm": "feed_w",
        "thickness_mm": "patch_h",
    })

    _apply_macro(cst, generator, "create_port", {
        "port_id": 1,
        "impedance_ohm": 50,
        "p1_mm": {"x": "feed_x", "y": "-sub_l/2", "z": "sub_h"},
        "p2_mm": {"x": "feed_x", "y": "-sub_l/2", "z": "patch_h"},
        "calculate_port_extension": False,
    })
    _apply_macro(cst, generator, "set_boundary", {"boundary_type": "expanded_open", "padding_mm": 10})
    _apply_macro(cst, generator, "set_solver", {"solver_type": "time_domain", "mesh_cells_per_wavelength": 20})
    _apply_macro(cst, generator, "add_farfield_monitor", {
        "frequency_ghz": 2.4,
        "monitor_value": "ff_freq_ghz",
        "name": "farfield_dataset",
    })


def _parameter_updates(sample: SampleInput, geom: PatchGeometry) -> dict[str, float]:
    margin_ghz = max(0.3, sample.target_bandwidth_mhz / 1000.0)
    return {
        "sub_w": geom.substrate_width_mm,
        "sub_l": geom.substrate_length_mm,
        "sub_h": sample.substrate_height_mm,
        "patch_w": geom.patch_width_mm,
        "patch_l": geom.patch_length_mm,
        "patch_h": geom.patch_height_mm,
        "feed_w": geom.feed_width_mm,
        "feed_x": geom.feed_offset_x_mm,
        "freq_start_ghz": round(max(0.5, sample.target_frequency_ghz - margin_ghz), 4),
        "freq_stop_ghz": round(sample.target_frequency_ghz + margin_ghz, 4),
        "ff_freq_ghz": round(sample.target_frequency_ghz, 6),
        "er_sub": sample.substrate_epsilon_r,
        "tan_delta_sub": sample.substrate_loss_tangent,
        "sigma_cond": sample.conductor_conductivity_s_per_m,
    }


def _apply_parameter_updates(cst: CSTApp, updates: dict[str, float]) -> None:
    for name, value in updates.items():
        if not cst.set_parameter(name, value, create_only=False):
            raise RuntimeError(f"Failed to update CST parameter: {name}")
    if not cst.rebuild_model(full_history=False):
        raise RuntimeError("Failed to rebuild CST model after parameter updates")


def _recycle_project(cst: CSTApp, generator: VBAGenerator, project_name: str) -> None:
    try:
        cst.close_project(save=False)
    except Exception:
        pass
    _build_model(cst, generator, project_name=project_name)


def _relative_to_root(path: str | None) -> str:
    if not path:
        return ""
    raw = Path(path)
    try:
        return str(raw.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")
    except Exception:
        return str(raw).replace("\\", "/")


def _run_single_sample(
    cst: CSTApp,
    sample_index: int,
    sample: SampleInput,
    geom: PatchGeometry,
) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    destination_hint = f"{run_id}_farfield"
    started = time.perf_counter()
    solver_status = "success"
    notes = ""
    s11_path = ""
    farfield_path = ""
    actual_center_frequency_ghz = None
    actual_bandwidth_mhz = None
    actual_return_loss_db = None
    actual_vswr = None
    actual_gain_dbi = None
    actual_radiation_efficiency_pct = None
    actual_total_efficiency_pct = None
    actual_directivity_dbi = None
    actual_peak_theta_deg = None
    actual_peak_phi_deg = None
    actual_front_to_back_db = None
    actual_axial_ratio_db = None

    try:
        _apply_parameter_updates(cst, _parameter_updates(sample, geom))
        if not cst.run_simulation(timeout_sec=1200):
            raise RuntimeError("CST solver failed or timed out")

        s11_path = cst.export_s_parameters(destination_hint=f"{run_id}_s11") or ""
        s11_metrics = CSTApp.extract_summary_metrics(s11_path) if s11_path else None
        farfield_source = cst.export_farfield(sample.target_frequency_ghz, destination_hint=destination_hint) or ""
        farfield_metrics = cst.extract_farfield_metrics(destination_hint=destination_hint) if farfield_source else None
        farfield_path = farfield_source

        if s11_metrics:
            actual_center_frequency_ghz = s11_metrics.get("center_frequency")
            bandwidth_ghz = s11_metrics.get("bandwidth")
            actual_bandwidth_mhz = float(bandwidth_ghz) * 1000.0 if bandwidth_ghz is not None else None
            min_s11_db = s11_metrics.get("min_s11_db")
            actual_return_loss_db = abs(float(min_s11_db)) if min_s11_db is not None else None
            actual_vswr = _return_loss_to_vswr(actual_return_loss_db)

        if farfield_metrics:
            actual_gain_dbi = (
                farfield_metrics.get("max_realized_gain_dbi")
                or farfield_metrics.get("max_gain_dbi")
                or farfield_metrics.get("theta_cut_peak_gain_dbi")
            )
            actual_radiation_efficiency_pct = _db_to_percent(farfield_metrics.get("radiation_efficiency_db"))
            actual_total_efficiency_pct = _db_to_percent(farfield_metrics.get("total_efficiency_db"))
            actual_directivity_dbi = farfield_metrics.get("max_directivity_dbi")
            actual_peak_theta_deg = farfield_metrics.get("main_lobe_direction_deg")
            actual_peak_phi_deg = 0.0 if actual_peak_theta_deg is not None else None
            actual_front_to_back_db = farfield_metrics.get("front_to_back_ratio_db")
            actual_axial_ratio_db = None
            notes = farfield_metrics.get("warning", "")

        if actual_center_frequency_ghz is None or actual_bandwidth_mhz is None:
            solver_status = "missing_metrics"
            if not notes:
                notes = "Simulation finished but CST metric extraction was incomplete."
    except Exception as exc:
        solver_status = "failed"
        notes = str(exc)
        logger.exception("Dataset sample %s failed", sample_index)
    simulation_time_sec = time.perf_counter() - started
    row = {
        "run_id": run_id,
        "timestamp_utc": timestamp_utc,
        "antenna_family": "microstrip_patch",
        "patch_shape": "rectangular",
        "feed_type": "edge",
        "polarization": "linear",
        "substrate_name": sample.substrate_name,
        "conductor_name": sample.conductor_name,
        "target_frequency_ghz": _round(sample.target_frequency_ghz, 6),
        "target_bandwidth_mhz": _round(sample.target_bandwidth_mhz, 3),
        "target_minimum_gain_dbi": _round(sample.target_minimum_gain_dbi, 3),
        "target_maximum_vswr": _round(sample.target_maximum_vswr, 3),
        "target_minimum_return_loss_db": _round(sample.target_minimum_return_loss_db, 3),
        "substrate_epsilon_r": _round(sample.substrate_epsilon_r, 4),
        "substrate_height_mm": _round(sample.substrate_height_mm, 4),
        "patch_length_mm": _round(geom.patch_length_mm, 4),
        "patch_width_mm": _round(geom.patch_width_mm, 4),
        "patch_height_mm": _round(geom.patch_height_mm, 4),
        "substrate_length_mm": _round(geom.substrate_length_mm, 4),
        "substrate_width_mm": _round(geom.substrate_width_mm, 4),
        "feed_length_mm": _round(geom.feed_length_mm, 4),
        "feed_width_mm": _round(geom.feed_width_mm, 4),
        "feed_offset_x_mm": _round(geom.feed_offset_x_mm, 4),
        "feed_offset_y_mm": _round(geom.feed_offset_y_mm, 4),
        "actual_center_frequency_ghz": _round(actual_center_frequency_ghz, 6),
        "actual_bandwidth_mhz": _round(actual_bandwidth_mhz, 3),
        "actual_return_loss_db": _round(actual_return_loss_db, 3),
        "actual_vswr": _round(actual_vswr, 4),
        "actual_gain_dbi": _round(actual_gain_dbi, 3),
        "actual_radiation_efficiency_pct": _round(actual_radiation_efficiency_pct, 3),
        "actual_total_efficiency_pct": _round(actual_total_efficiency_pct, 3),
        "actual_directivity_dbi": _round(actual_directivity_dbi, 3),
        "actual_peak_theta_deg": _round(actual_peak_theta_deg, 3),
        "actual_peak_phi_deg": _round(actual_peak_phi_deg, 3),
        "actual_front_to_back_db": _round(actual_front_to_back_db, 3),
        "actual_axial_ratio_db": _round(actual_axial_ratio_db, 3),
        "accepted": "",
        "solver_status": solver_status,
        "simulation_time_sec": _round(simulation_time_sec, 3),
        "notes": notes,
        "farfield_artifact_path": _relative_to_root(farfield_path),
        "s11_artifact_path": _relative_to_root(s11_path),
    }
    row["accepted"] = _to_bool_text(_accepted(row))
    return row


def main() -> int:
    global _ACTIVE_CST
    parser = argparse.ArgumentParser(description="Generate CST-backed raw feedback rows for rectangular patch ANN training.")
    parser.add_argument("--samples", type=int, default=1, help="Number of CST runs to execute.")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducibility.")
    parser.add_argument("--output", default=str(RAW_DATA_PATH), help="CSV output path.")
    parser.add_argument("--baseline-only", action="store_true", help="Disable perturbations and log pure recipe geometry.")
    parser.add_argument(
        "--recycle-every",
        type=int,
        default=20,
        help="Close and recreate the CST project after this many completed samples. Use 0 to disable.",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _sigint_handler)

    rng = random.Random(args.seed)
    output_path = Path(args.output)

    cst = CSTApp()
    _ACTIVE_CST = cst
    if not cst.connect():
        raise SystemExit("Failed to connect to CST. Start CST Studio and rerun.")

    generator = VBAGenerator()
    project_name = "rect_patch_feedback_working"

    _build_model(cst, generator, project_name=project_name)

    completed = 0
    try:
        for index in range(args.samples):
            if _SHUTDOWN.is_set():
                print(f"Stopping early after {completed} of {args.samples} samples.", flush=True)
                break
            if args.recycle_every > 0 and completed > 0 and completed % args.recycle_every == 0:
                print(
                    f"Recycling CST project after {completed} completed samples to limit in-memory result buildup.",
                    flush=True,
                )
                _recycle_project(cst, generator, project_name=project_name)
            sample = _sample_input(rng)
            base_geom = _baseline_geometry(sample)
            geom = base_geom if args.baseline_only else _perturb_geometry(base_geom, rng)
            row = _run_single_sample(cst, index, sample, geom)
            _append_csv_row(row, output_path)
            print(json.dumps(row, indent=2))
            completed += 1
    except KeyboardInterrupt:
        print(f"Interrupted after {completed} completed samples.", flush=True)
        return 130
    finally:
        try:
            cst.disconnect()
        except Exception:
            pass
        _ACTIVE_CST = None

    return 0


if __name__ == "__main__":
    raise SystemExit(main())