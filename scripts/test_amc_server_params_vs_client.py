#!/usr/bin/env python3
"""Compare AMC CST performance: client-derived geometry vs server-family-parameter geometry.

Workflow:
1) Request AMC optimize package from server.
2) Build and execute CST model with client heuristic AMC synthesis.
3) Build and execute CST model with server-provided AMC family parameters.
4) Compare extracted CST metrics and report the better strategy.
"""

from __future__ import annotations

import asyncio
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from comm.api_client import ApiClient
from comm.request_builder import RequestBuilder
from comm.server_connector import ServerConnector
from cst_client.cst_app import CSTApp
from executor.command_parser import CommandParser, CommandPackage
from executor.execution_engine import ExecutionEngine
from scripts.run_amc_pipeline_once import (
    _extract_scalar_dimensions,
    _family_of,
    _has_amc_geometry,
    _inject_amc_geometry_if_missing,
    _load_config,
    _materialize_primary_patch_geometry,
    _resequence,
    _to_vswr_from_return_loss,
)
from utils.logger import get_logger

logger = get_logger(__name__)

REPORTS_DIR = PROJECT_ROOT / "artifacts" / "reports"
DEFAULT_TIMEOUT_SEC = 60


@dataclass
class StrategyResult:
    strategy: str
    session_id: str
    trace_id: str
    design_id: str
    command_count: int
    dry_run: bool
    s11_metrics: Optional[dict[str, Any]]
    farfield_metrics: Optional[dict[str, Any]]
    artifacts: dict[str, Any]
    score: float


def _safe_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_family_params(package_data: dict[str, Any]) -> dict[str, Any]:
    recipe = package_data.get("design_recipe") if isinstance(package_data.get("design_recipe"), dict) else {}
    recipe_family = recipe.get("family_parameters") if isinstance(recipe.get("family_parameters"), dict) else {}
    package_family = package_data.get("family_parameters") if isinstance(package_data.get("family_parameters"), dict) else {}
    merged = dict(recipe_family)
    merged.update(package_family)
    return merged


def _build_amc_commands_from_server(base_dims: dict[str, float], family_params: dict[str, Any], component: str = "amc") -> list[dict[str, Any]]:
    px = base_dims["px"]
    py = base_dims["py"]
    sx = base_dims["sx"]
    sy = base_dims["sy"]
    h_sub = base_dims["h_sub"]
    t_cu = base_dims["t_cu"]
    f0 = max(0.1, base_dims["f0"])

    wavelength_mm = 300.0 / f0

    period_fallback = max(0.14 * wavelength_mm, min(0.65 * max(px, py), 0.24 * wavelength_mm))
    amc_period = _safe_float(family_params.get("amc_unit_cell_period_mm"), period_fallback)
    amc_period = max(1.0, amc_period)

    amc_cell = _safe_float(family_params.get("amc_patch_size_mm"), 0.90 * amc_period)
    amc_cell = max(0.1, min(amc_cell, amc_period - 0.05))

    amc_gap = _safe_float(family_params.get("amc_gap_mm"), amc_period - amc_cell)
    amc_gap = max(0.05, amc_gap)

    amc_air_gap = _safe_float(family_params.get("amc_air_gap_mm"), max(2.0, 0.02 * wavelength_mm))
    amc_air_gap = max(0.0, amc_air_gap)

    amc_sub_h = _safe_float(
        family_params.get("amc_via_height_mm"),
        max(1.0, 0.5 * h_sub),
    )
    amc_sub_h = max(0.2, amc_sub_h)

    nx_fallback = max(5, min(11, int(round(sx / amc_period)) or 7))
    ny_fallback = max(5, min(11, int(round(sy / amc_period)) or 7))

    amc_nx = int(round(_safe_float(family_params.get("amc_array_cols"), nx_fallback)))
    amc_ny = int(round(_safe_float(family_params.get("amc_array_rows"), ny_fallback)))

    amc_nx = max(3, min(21, amc_nx))
    amc_ny = max(3, min(21, amc_ny))
    if amc_nx % 2 == 0:
        amc_nx += 1
    if amc_ny % 2 == 0:
        amc_ny += 1

    amc_size_x = amc_nx * amc_period
    amc_size_y = amc_ny * amc_period

    amc_cell_z0 = -t_cu - amc_air_gap
    amc_cell_z1 = amc_cell_z0 + t_cu
    amc_sub_z1 = amc_cell_z0
    amc_sub_z0 = amc_sub_z1 - amc_sub_h
    amc_gnd_z1 = amc_sub_z0
    amc_gnd_z0 = amc_gnd_z1 - t_cu

    commands: list[dict[str, Any]] = [
        {
            "command": "create_component",
            "params": {"component": component},
            "on_failure": "abort",
            "checksum_scope": "geometry",
        },
        {
            "command": "define_parameter",
            "params": {"name": "amc_period", "value": amc_period},
            "on_failure": "abort",
            "checksum_scope": "geometry",
        },
        {
            "command": "define_parameter",
            "params": {"name": "amc_cell", "value": amc_cell},
            "on_failure": "abort",
            "checksum_scope": "geometry",
        },
        {
            "command": "define_parameter",
            "params": {"name": "amc_gap", "value": amc_gap},
            "on_failure": "abort",
            "checksum_scope": "geometry",
        },
        {
            "command": "define_parameter",
            "params": {"name": "amc_nx", "value": amc_nx},
            "on_failure": "abort",
            "checksum_scope": "geometry",
        },
        {
            "command": "define_parameter",
            "params": {"name": "amc_ny", "value": amc_ny},
            "on_failure": "abort",
            "checksum_scope": "geometry",
        },
        {
            "command": "define_parameter",
            "params": {"name": "amc_air_gap", "value": amc_air_gap},
            "on_failure": "abort",
            "checksum_scope": "geometry",
        },
        {
            "command": "define_parameter",
            "params": {"name": "amc_sub_h", "value": amc_sub_h},
            "on_failure": "abort",
            "checksum_scope": "geometry",
        },
        {
            "command": "define_brick",
            "params": {
                "name": "amc_substrate",
                "component": component,
                "material": "FR-4_(lossy)",
                "xrange": [-amc_size_x / 2.0, amc_size_x / 2.0],
                "yrange": [-amc_size_y / 2.0, amc_size_y / 2.0],
                "zrange": [amc_sub_z0, amc_sub_z1],
            },
            "on_failure": "abort",
            "checksum_scope": "geometry",
        },
        {
            "command": "define_brick",
            "params": {
                "name": "amc_ground",
                "component": component,
                "material": "Copper_(annealed)",
                "xrange": [-amc_size_x / 2.0, amc_size_x / 2.0],
                "yrange": [-amc_size_y / 2.0, amc_size_y / 2.0],
                "zrange": [amc_gnd_z0, amc_gnd_z1],
            },
            "on_failure": "abort",
            "checksum_scope": "geometry",
        },
    ]

    x0 = -(amc_nx - 1) * amc_period / 2.0
    y0 = -(amc_ny - 1) * amc_period / 2.0
    for ix in range(amc_nx):
        for iy in range(amc_ny):
            cx = x0 + ix * amc_period
            cy = y0 + iy * amc_period
            commands.append(
                {
                    "command": "define_brick",
                    "params": {
                        "name": f"amc_cell_{ix}_{iy}",
                        "component": component,
                        "material": "Copper_(annealed)",
                        "xrange": [cx - (amc_cell / 2.0), cx + (amc_cell / 2.0)],
                        "yrange": [cy - (amc_cell / 2.0), cy + (amc_cell / 2.0)],
                        "zrange": [amc_cell_z0, amc_cell_z1],
                    },
                    "on_failure": "abort",
                    "checksum_scope": "geometry",
                }
            )

    return commands


def _inject_amc_geometry_from_server_params(package_data: dict[str, Any]) -> dict[str, Any]:
    package_data = _materialize_primary_patch_geometry(package_data)
    if _family_of(package_data) != "amc_patch":
        return package_data

    commands = list(package_data.get("commands") or [])
    if not commands:
        return package_data
    if not any(str(c.get("command", "")).strip() == "create_project" for c in commands):
        return package_data
    if _has_amc_geometry(commands):
        return package_data

    base_dims = _extract_scalar_dimensions(package_data, commands)
    family_params = _extract_family_params(package_data)
    amc_commands = _build_amc_commands_from_server(base_dims, family_params)

    rebuild_index = next(
        (idx for idx, cmd in enumerate(commands) if str(cmd.get("command", "")).strip() == "rebuild_model"),
        len(commands),
    )
    enriched = commands[:rebuild_index] + amc_commands + commands[rebuild_index:]

    patched = dict(package_data)
    patched["commands"] = _resequence(enriched)

    recipe = dict(patched.get("design_recipe") or {})
    notes = list(recipe.get("notes") or [])
    notes.append("Client used server AMC family_parameters to build AMC unit-cell geometry.")
    recipe["notes"] = notes
    patched["design_recipe"] = recipe
    return patched


def _extract_metrics_from_artifacts(artifacts: dict[str, Any]) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
    s11_metrics: Optional[dict[str, Any]] = None
    farfield_metrics: Optional[dict[str, Any]] = None

    s11_trace_path = artifacts.get("s11_trace_path")
    if s11_trace_path:
        s11_path = Path(str(s11_trace_path))
        if s11_path.exists():
            s11_metrics = CSTApp.extract_summary_metrics(str(s11_path))

    farfield_metrics_path = artifacts.get("farfield_metrics_path")
    if farfield_metrics_path:
        ff_path = Path(str(farfield_metrics_path))
        if ff_path.exists():
            try:
                farfield_metrics = json.loads(ff_path.read_text(encoding="utf-8"))
            except Exception:
                farfield_metrics = None

    return s11_metrics, farfield_metrics


def _score_metrics(s11_metrics: Optional[dict[str, Any]], farfield_metrics: Optional[dict[str, Any]]) -> float:
    min_s11_db = _safe_float((s11_metrics or {}).get("min_s11_db"), -5.0)
    gain_dbi = _safe_float(
        (farfield_metrics or {}).get("max_realized_gain_dbi")
        or (farfield_metrics or {}).get("max_gain_dbi"),
        0.0,
    )
    vswr = _to_vswr_from_return_loss(abs(min_s11_db))
    s11_reward = abs(min_s11_db)
    vswr_penalty = max(0.0, vswr - 1.0)
    score = gain_dbi + (0.15 * s11_reward) - (0.25 * vswr_penalty)
    return float(score)


async def _run_strategy(
    *,
    base_url: str,
    timeout_sec: int,
    strategy_name: str,
    injector,
) -> StrategyResult:
    connector = ServerConnector(base_url, timeout_sec=timeout_sec)
    async with connector:
        api = ApiClient(connector)
        request = RequestBuilder().build_optimize_request(
            user_text="Design an AMC-backed microstrip patch antenna at 2.45 GHz with 100 MHz bandwidth and maximize gain improvement.",
            design_specs={
                "frequency_ghz": 2.45,
                "bandwidth_mhz": 100.0,
                "antenna_family": "amc_patch",
                "patch_shape": "auto",
                "feed_type": "auto",
                "polarization": "unspecified",
            },
        )
        optimize_response = await api.optimize(request.model_dump())

    if optimize_response.status not in ("accepted", "completed"):
        raise RuntimeError(f"{strategy_name}: optimize status {optimize_response.status}")
    if not optimize_response.command_package:
        raise RuntimeError(f"{strategy_name}: missing command package")

    package_data = injector(dict(optimize_response.command_package))
    parser = CommandParser()
    package = parser.parse_package(package_data)
    parser.validate_package(package)

    engine = ExecutionEngine()
    results = await engine.execute_command_package(package)
    if engine.dry_run:
        raise RuntimeError("CST dry-run mode detected. Start CST and rerun.")

    non_optional_failed = [r for r in results if (not r.success and str(r.command_id).split(":", 1)[-1] != "export_farfield")]
    if non_optional_failed:
        raise RuntimeError(
            f"{strategy_name}: non-optional commands failed: " + ", ".join(r.command_id for r in non_optional_failed)
        )

    artifacts = engine.get_artifacts()
    s11_metrics, farfield_metrics = _extract_metrics_from_artifacts(artifacts)
    score = _score_metrics(s11_metrics, farfield_metrics)

    return StrategyResult(
        strategy=strategy_name,
        session_id=optimize_response.session_id,
        trace_id=optimize_response.trace_id,
        design_id=package.design_id,
        command_count=len(package.commands),
        dry_run=engine.dry_run,
        s11_metrics=s11_metrics,
        farfield_metrics=farfield_metrics,
        artifacts=artifacts,
        score=score,
    )


async def run_comparison() -> int:
    config = _load_config()
    server_cfg = config.get("server", {})
    base_url = str(server_cfg.get("base_url", "http://192.168.29.147:8000"))
    timeout_sec = int(server_cfg.get("timeout_sec", DEFAULT_TIMEOUT_SEC))

    logger.info("AMC strategy comparison: health check")
    connector = ServerConnector(base_url, timeout_sec=timeout_sec)
    async with connector:
        api = ApiClient(connector)
        health = await api.health_check()
    if health.get("status") != "ok":
        raise RuntimeError(f"Server health not ok: {health}")

    logger.info("Running strategy A: client heuristic AMC synthesis")
    result_client = await _run_strategy(
        base_url=base_url,
        timeout_sec=timeout_sec,
        strategy_name="client_heuristic",
        injector=_inject_amc_geometry_if_missing,
    )

    logger.info("Running strategy B: server family-parameter AMC synthesis")
    result_server = await _run_strategy(
        base_url=base_url,
        timeout_sec=timeout_sec,
        strategy_name="server_family_parameters",
        injector=_inject_amc_geometry_from_server_params,
    )

    winner = "tie"
    if not math.isclose(result_client.score, result_server.score, rel_tol=1e-9, abs_tol=1e-9):
        winner = result_client.strategy if result_client.score > result_server.score else result_server.strategy

    summary = {
        "started_at": datetime.now().isoformat(),
        "server": base_url,
        "winner": winner,
        "results": {
            result_client.strategy: {
                "session_id": result_client.session_id,
                "trace_id": result_client.trace_id,
                "design_id": result_client.design_id,
                "command_count": result_client.command_count,
                "score": result_client.score,
                "s11_metrics": result_client.s11_metrics,
                "farfield_metrics": result_client.farfield_metrics,
                "artifacts": result_client.artifacts,
            },
            result_server.strategy: {
                "session_id": result_server.session_id,
                "trace_id": result_server.trace_id,
                "design_id": result_server.design_id,
                "command_count": result_server.command_count,
                "score": result_server.score,
                "s11_metrics": result_server.s11_metrics,
                "farfield_metrics": result_server.farfield_metrics,
                "artifacts": result_server.artifacts,
            },
        },
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"amc_server_vs_client_compare_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    logger.info(f"Winner: {winner}")
    logger.info(f"client_heuristic score: {result_client.score:.4f}")
    logger.info(f"server_family_parameters score: {result_server.score:.4f}")
    logger.info(f"Report: {report_path}")

    return 0


async def _main() -> int:
    try:
        return await run_comparison()
    except Exception as exc:
        logger.error(f"AMC strategy comparison failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
