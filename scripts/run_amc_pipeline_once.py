#!/usr/bin/env python3
"""Run one full AMC optimize -> CST execute -> feedback loop against the server."""

from __future__ import annotations

import asyncio
import json
import sys
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
from utils.logger import get_logger

logger = get_logger(__name__)

CONFIG_PATH = PROJECT_ROOT / "config.json"
REPORTS_DIR = PROJECT_ROOT / "artifacts" / "reports"
EXPORTS_DIR = PROJECT_ROOT / "artifacts" / "exports"
DEFAULT_MAX_ITERATIONS = 5


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _as_float(value: Any, default: float) -> float:
    if _is_number(value):
        return float(value)
    return default


def _family_of(package_data: dict[str, Any]) -> str:
    recipe = package_data.get("design_recipe") or {}
    family = str(recipe.get("family", "")).strip()
    if family:
        return family
    dims = package_data.get("predicted_dimensions") or {}
    if "amc_period_mm" in dims:
        return "amc_patch"
    return ""


def _has_amc_geometry(commands: list[dict[str, Any]]) -> bool:
    for cmd in commands:
        if str(cmd.get("command", "")).strip() != "define_brick":
            continue
        name = str((cmd.get("params") or {}).get("name", "")).strip().lower()
        if name.startswith("amc_"):
            return True
    return False


def _resequence(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resequenced: list[dict[str, Any]] = []
    for index, cmd in enumerate(commands, start=1):
        patched = dict(cmd)
        patched["seq"] = index
        resequenced.append(patched)
    return resequenced


def _extract_scalar_dimensions(package_data: dict[str, Any], commands: list[dict[str, Any]]) -> dict[str, float]:
    dims = dict(package_data.get("predicted_dimensions") or {})
    params_from_cmds: dict[str, float] = {}
    for cmd in commands:
        cname = str(cmd.get("command", "")).strip()
        if cname not in {"define_parameter", "update_parameter"}:
            continue
        payload = cmd.get("params") or {}
        pname = str(payload.get("name", "")).strip()
        pvalue = payload.get("value")
        if pname and _is_number(pvalue):
            params_from_cmds[pname] = float(str(pvalue))

    px = _as_float(params_from_cmds.get("px", dims.get("patch_width_mm")), 37.0)
    py = _as_float(params_from_cmds.get("py", dims.get("patch_length_mm")), 29.0)
    sx = _as_float(params_from_cmds.get("sx", dims.get("substrate_width_mm")), 55.0)
    sy = _as_float(params_from_cmds.get("sy", dims.get("substrate_length_mm")), 47.0)
    h_sub = _as_float(params_from_cmds.get("h_sub", dims.get("substrate_height_mm")), 3.0)
    t_cu = _as_float(params_from_cmds.get("t_cu", dims.get("patch_height_mm")), 0.035)
    feed_x = _as_float(params_from_cmds.get("feed_x", dims.get("feed_offset_x_mm")), 0.0)
    feed_w = _as_float(params_from_cmds.get("feed_w", dims.get("feed_width_mm")), 2.0)
    f0 = _as_float((package_data.get("predicted_metrics") or {}).get("center_frequency_ghz"), 2.45)

    return {
        "px": px,
        "py": py,
        "sx": sx,
        "sy": sy,
        "h_sub": h_sub,
        "t_cu": t_cu,
        "feed_x": feed_x,
        "feed_w": feed_w,
        "f0": f0,
    }


def _materialize_primary_patch_geometry(package_data: dict[str, Any]) -> dict[str, Any]:
    commands = list(package_data.get("commands") or [])
    if not commands:
        return package_data
    if not any(str(c.get("command", "")).strip() == "create_project" for c in commands):
        return package_data

    dims = _extract_scalar_dimensions(package_data, commands)
    px = dims["px"]
    py = dims["py"]
    sx = dims["sx"]
    sy = dims["sy"]
    h_sub = dims["h_sub"]
    t_cu = dims["t_cu"]
    feed_x = dims["feed_x"]
    feed_w = dims["feed_w"]

    updated: list[dict[str, Any]] = []
    for cmd in commands:
        cname = str(cmd.get("command", "")).strip()
        if cname != "define_brick":
            updated.append(cmd)
            continue

        params = dict(cmd.get("params") or {})
        component = str(params.get("component", "")).strip().lower()
        name = str(params.get("name", "")).strip().lower()

        if component != "antenna":
            updated.append(cmd)
            continue

        if name == "substrate":
            params["xrange"] = [-sx / 2.0, sx / 2.0]
            params["yrange"] = [-sy / 2.0, sy / 2.0]
            params["zrange"] = [0.0, h_sub]
        elif name == "ground":
            params["xrange"] = [-sx / 2.0, sx / 2.0]
            params["yrange"] = [-sy / 2.0, sy / 2.0]
            params["zrange"] = [-t_cu, 0.0]
        elif name == "patch":
            params["xrange"] = [-px / 2.0, px / 2.0]
            params["yrange"] = [-py / 2.0, py / 2.0]
            params["zrange"] = [h_sub, h_sub + t_cu]
        elif name == "feed":
            params["xrange"] = [feed_x - (feed_w / 2.0), feed_x + (feed_w / 2.0)]
            params["yrange"] = [-sy / 2.0, -py / 2.0]
            params["zrange"] = [h_sub, h_sub + t_cu]
        else:
            updated.append(cmd)
            continue

        patched = dict(cmd)
        patched["params"] = params
        updated.append(patched)

    package_data = dict(package_data)
    package_data["commands"] = _resequence(updated)
    return package_data


def _build_amc_commands(base_dims: dict[str, float], component: str = "amc") -> list[dict[str, Any]]:
    px = base_dims["px"]
    py = base_dims["py"]
    sx = base_dims["sx"]
    sy = base_dims["sy"]
    h_sub = base_dims["h_sub"]
    t_cu = base_dims["t_cu"]
    f0 = max(0.1, base_dims["f0"])

    wavelength_mm = 300.0 / f0
    period_min = 0.14 * wavelength_mm
    period_max = 0.24 * wavelength_mm
    period_seed = 0.65 * max(px, py)
    amc_period = max(period_min, min(period_seed, period_max))
    amc_cell = 0.90 * amc_period
    amc_gap = amc_period - amc_cell
    amc_air_gap = max(2.0, 0.02 * wavelength_mm)
    amc_sub_h = max(1.0, 0.5 * h_sub)

    nx_seed = int(round(sx / amc_period))
    ny_seed = int(round(sy / amc_period))
    amc_nx = max(5, min(11, nx_seed if nx_seed > 0 else 7))
    amc_ny = max(5, min(11, ny_seed if ny_seed > 0 else 7))
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


def _inject_amc_geometry_if_missing(package_data: dict[str, Any]) -> dict[str, Any]:
    package_data = _materialize_primary_patch_geometry(package_data)
    family = _family_of(package_data)
    if family != "amc_patch":
        return package_data

    commands = list(package_data.get("commands") or [])
    if not commands:
        return package_data
    if not any(str(c.get("command", "")).strip() == "create_project" for c in commands):
        return package_data
    if _has_amc_geometry(commands):
        return package_data

    dims = _extract_scalar_dimensions(package_data, commands)
    amc_commands = _build_amc_commands(dims)

    rebuild_index = next(
        (idx for idx, cmd in enumerate(commands) if str(cmd.get("command", "")).strip() == "rebuild_model"),
        len(commands),
    )

    enriched = commands[:rebuild_index] + amc_commands + commands[rebuild_index:]
    package_data = dict(package_data)
    package_data["commands"] = _resequence(enriched)

    design_recipe = dict(package_data.get("design_recipe") or {})
    notes = list(design_recipe.get("notes") or [])
    notes.append(
        "Client added AMC unit-cell array layer (period/gap/air-gap + N x N duplicated cells) before simulation."
    )
    design_recipe["notes"] = notes
    package_data["design_recipe"] = design_recipe
    return package_data


def _load_config() -> dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _to_vswr_from_return_loss(return_loss_db: float) -> float:
    if return_loss_db <= 0:
        return 99.0
    gamma = 10 ** (-return_loss_db / 20.0)
    if gamma >= 1.0:
        return 99.0
    vswr = (1.0 + gamma) / (1.0 - gamma)
    if vswr > 100.0:
        return 99.0
    return vswr


def _build_feedback_payload(
    package: CommandPackage,
    session_id: str,
    trace_id: str,
    design_id: str,
    s11_metrics: Optional[dict[str, Any]],
    s11_path: Optional[Path],
    farfield_metrics: Optional[dict[str, Any]],
    farfield_metrics_path: Optional[Path],
) -> dict[str, Any]:
    center_frequency_ghz = float((s11_metrics or {}).get("center_frequency", 2.45))
    bandwidth_ghz = float((s11_metrics or {}).get("bandwidth", 0.1))
    min_s11_db = float((s11_metrics or {}).get("min_s11_db", -10.0))
    return_loss_db = min_s11_db
    vswr = _to_vswr_from_return_loss(abs(min_s11_db))

    gain_dbi = 0.0
    if farfield_metrics:
        gain_dbi = float(
            farfield_metrics.get("max_realized_gain_dbi")
            or farfield_metrics.get("max_gain_dbi")
            or 0.0
        )

    payload = {
        "schema_version": "client_feedback.v1",
        "session_id": session_id,
        "trace_id": trace_id,
        "design_id": design_id,
        "iteration_index": int(package.iteration_index),
        "simulation_status": "completed",
        "actual_center_frequency_ghz": round(center_frequency_ghz, 6),
        "actual_bandwidth_mhz": round(bandwidth_ghz * 1000.0, 3),
        "actual_return_loss_db": round(return_loss_db, 3),
        "actual_vswr": round(vswr, 4),
        "actual_gain_dbi": round(gain_dbi, 3),
        "notes": "One-pass AMC CST-backed pipeline validation run.",
        "artifacts": {
            "s11_trace_ref": str(s11_path.resolve()) if s11_path else None,
            "summary_metrics_ref": str((EXPORTS_DIR / "summary_metrics_amc.json").resolve()),
            "farfield_ref": str(farfield_metrics_path.resolve()) if farfield_metrics_path else None,
            "current_distribution_ref": None,
        },
    }

    return payload


def _resolve_metrics_from_execution_artifacts(
    artifacts: dict[str, Any],
) -> tuple[Optional[dict[str, Any]], Optional[Path], Optional[dict[str, Any]], Optional[Path]]:
    s11_path = Path(str(artifacts.get("s11_trace_path"))).resolve() if artifacts.get("s11_trace_path") else None
    farfield_metrics_path = (
        Path(str(artifacts.get("farfield_metrics_path"))).resolve()
        if artifacts.get("farfield_metrics_path")
        else None
    )

    s11_metrics = None
    if s11_path and s11_path.exists():
        s11_metrics = CSTApp.extract_summary_metrics(str(s11_path))

    farfield_metrics = None
    if farfield_metrics_path and farfield_metrics_path.exists():
        try:
            farfield_metrics = json.loads(farfield_metrics_path.read_text(encoding="utf-8"))
        except Exception:
            farfield_metrics = None

    return s11_metrics, s11_path, farfield_metrics, farfield_metrics_path


async def run_once() -> int:
    config = _load_config()
    server_cfg = config.get("server", {})
    base_url = server_cfg.get("base_url", "http://192.168.29.147:8000")
    timeout_sec = int(server_cfg.get("timeout_sec", 60))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "started_at": datetime.now().isoformat(),
        "server": base_url,
        "steps": {},
    }

    logger.info("STEP 1/4: Health check")
    connector = ServerConnector(base_url, timeout_sec=timeout_sec)
    async with connector:
        api = ApiClient(connector)
        health = await api.health_check()
        report["steps"]["health"] = health
        if health.get("status") != "ok":
            raise RuntimeError(f"Server health not ok: {health}")

        logger.info("STEP 2/4: AMC optimize request")
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
        raise RuntimeError(f"Unexpected optimize status: {optimize_response.status}")

    if not optimize_response.command_package:
        raise RuntimeError("Optimize response did not include command_package")

    session_id = optimize_response.session_id or ""
    trace_id = optimize_response.trace_id or ""
    design_id = str(optimize_response.command_package.get("design_id") or "")

    if not session_id or not trace_id or not design_id:
        raise RuntimeError("Missing session_id, trace_id, or design_id in optimize response")

    report["steps"]["optimize"] = {
        "status": optimize_response.status,
        "session_id": session_id,
        "trace_id": trace_id,
        "design_id": design_id,
        "command_count": len(optimize_response.command_package.get("commands", [])),
    }

    logger.info("STEP 3/4: CST execution + feedback loop")
    parser = CommandParser()
    initial_package_data = _inject_amc_geometry_if_missing(optimize_response.command_package)
    package = parser.parse_package(initial_package_data)
    parser.validate_package(package)

    max_iterations = DEFAULT_MAX_ITERATIONS
    optional_failures = {"export_farfield", "extract_farfield_metrics", "add_farfield_monitor"}
    loop_runs: list[dict[str, Any]] = []
    engine = ExecutionEngine()

    for loop_index in range(max_iterations):
        logger.info(f"Executing CST iteration {loop_index} (package iteration_index={package.iteration_index})")
        execution_results = await engine.execute_command_package(package)
        exec_progress = engine.get_progress()
        execution_artifacts = engine.get_artifacts()

        iteration_report: dict[str, Any] = {
            "loop_index": loop_index,
            "package_iteration_index": int(package.iteration_index),
            "design_id": package.design_id,
            "execution": {
                "dry_run": engine.dry_run,
                "progress": exec_progress,
                "results": [r.to_dict() for r in execution_results],
                "artifacts": execution_artifacts,
            },
        }

        if engine.dry_run:
            raise RuntimeError(
                "Execution ran in dry-run mode (CST unavailable). Start CST and rerun for real validation."
            )

        failed_results = [r for r in execution_results if not r.success]
        non_optional_failed = []
        for failed in failed_results:
            command_name = str(failed.command_id).split(":", 1)[-1]
            if command_name not in optional_failures:
                non_optional_failed.append(failed)

        iteration_report["execution"]["optional_failure_count"] = len(failed_results) - len(non_optional_failed)
        iteration_report["execution"]["non_optional_failure_count"] = len(non_optional_failed)

        if non_optional_failed:
            raise RuntimeError(
                "CST execution failed for non-optional command(s): "
                + ", ".join(r.command_id for r in non_optional_failed)
            )

        s11_metrics, s11_path, farfield_metrics, farfield_metrics_path = _resolve_metrics_from_execution_artifacts(
            execution_artifacts
        )

        summary_metrics_path = EXPORTS_DIR / f"summary_metrics_amc_iter{loop_index}.json"
        summary_metrics = {
            "s11_metrics": s11_metrics,
            "farfield_metrics": farfield_metrics,
        }
        summary_metrics_path.write_text(json.dumps(summary_metrics, indent=2), encoding="utf-8")

        if not s11_path:
            raise RuntimeError("Missing s11_trace_path from execution artifacts; cannot build valid feedback payload")

        logger.info(f"STEP 4/4: Send feedback for iteration {loop_index}")
        feedback_payload = _build_feedback_payload(
            package=package,
            session_id=session_id,
            trace_id=trace_id,
            design_id=package.design_id,
            s11_metrics=s11_metrics,
            s11_path=s11_path,
            farfield_metrics=farfield_metrics,
            farfield_metrics_path=farfield_metrics_path,
        )
        feedback_payload["artifacts"]["summary_metrics_ref"] = str(summary_metrics_path.resolve())

        connector_fb = ServerConnector(base_url, timeout_sec=timeout_sec)
        async with connector_fb:
            api_fb = ApiClient(connector_fb)
            feedback_response = await api_fb.send_feedback(feedback_payload)

        iteration_report["feedback"] = {
            "request": feedback_payload,
            "response": feedback_response,
        }
        loop_runs.append(iteration_report)

        if feedback_response.get("status") == "completed":
            logger.info("Server marked design as completed; stopping loop")
            break

        next_package_data = feedback_response.get("next_command_package")
        if not next_package_data:
            logger.info("No next_command_package returned; stopping loop")
            break

        next_package_data = _inject_amc_geometry_if_missing(next_package_data)
        package = parser.parse_package(next_package_data)
        parser.validate_package(package)

    report["steps"]["loop"] = {
        "max_iterations": max_iterations,
        "executed_iterations": len(loop_runs),
        "runs": loop_runs,
    }

    report["finished_at"] = datetime.now().isoformat()
    report["status"] = "success"

    out_path = REPORTS_DIR / f"amc_pipeline_once_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info("AMC pipeline one-pass run succeeded")
    logger.info(f"Session: {session_id}")
    logger.info(f"Trace: {trace_id}")
    logger.info(f"Report: {out_path}")

    return 0


async def _main() -> int:
    try:
        return await run_once()
    except Exception as exc:
        logger.error(f"AMC one-pass pipeline failed: {exc}")
        failure_report = {
            "started_at": datetime.now().isoformat(),
            "status": "failed",
            "error": str(exc),
        }
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = REPORTS_DIR / f"amc_pipeline_once_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        out_path.write_text(json.dumps(failure_report, indent=2), encoding="utf-8")
        logger.info(f"Failure report: {out_path}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
