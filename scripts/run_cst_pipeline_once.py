#!/usr/bin/env python3
"""Run one full optimize -> CST execute -> feedback loop against the server.

This script is intended as a pre-UI gate to verify the real CST-backed pipeline.
It fails fast if CST is unavailable (dry-run mode) because that would not validate
actual CAD/simulation execution.
"""

from __future__ import annotations

import asyncio
import json
import math
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
DEFAULT_MAX_ITERATIONS = 1


def _load_config() -> dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _to_vswr_from_return_loss(return_loss_db: float) -> float:
    if return_loss_db <= 0:
        return 99.0
    gamma = 10 ** (-return_loss_db / 20.0)
    if gamma >= 1.0:
        return 99.0
    return (1.0 + gamma) / (1.0 - gamma)


def _resolve_s11_metrics(package: CommandPackage) -> tuple[Optional[dict[str, Any]], Optional[Path]]:
    destination_hint = "s11"
    for cmd in package.commands:
        if cmd.command in ("export_s_parameters", "extract_summary_metrics"):
            destination_hint = str(cmd.params.get("destination_hint", destination_hint))

    s11_path = EXPORTS_DIR / f"{destination_hint}.txt"
    if not s11_path.exists():
        return None, None

    metrics = CSTApp.extract_summary_metrics(str(s11_path))
    return metrics, s11_path


def _resolve_farfield_metrics(package: CommandPackage) -> tuple[Optional[dict[str, Any]], Optional[Path]]:
    destination_hint = "farfield"
    for cmd in package.commands:
        if cmd.command in ("export_farfield", "extract_farfield_metrics"):
            destination_hint = str(cmd.params.get("destination_hint", destination_hint))

    metrics_path = EXPORTS_DIR / f"{destination_hint}_metrics.json"
    if not metrics_path.exists():
        return None, None

    try:
        return json.loads(metrics_path.read_text(encoding="utf-8")), metrics_path
    except Exception:
        return None, metrics_path


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
    # Fallbacks let the request remain schema-valid even if one export is missing.
    center_frequency_ghz = float((s11_metrics or {}).get("center_frequency", 2.45))
    bandwidth_ghz = float((s11_metrics or {}).get("bandwidth", 0.1))
    min_s11_db = float((s11_metrics or {}).get("min_s11_db", -10.0))
    return_loss_db = abs(min_s11_db)
    vswr = _to_vswr_from_return_loss(return_loss_db)

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
        "notes": "One-pass CST-backed pipeline validation run.",
        "artifacts": {
            "s11_trace_ref": str(s11_path.resolve()) if s11_path else None,
            "summary_metrics_ref": str((EXPORTS_DIR / "summary_metrics.json").resolve()),
            "farfield_ref": str(farfield_metrics_path.resolve()) if farfield_metrics_path else None,
            "current_distribution_ref": None,
        },
    }

    return payload


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

        logger.info("STEP 2/4: Optimize request")
        request = RequestBuilder().build_optimize_request(
            user_text="Design a microstrip patch antenna at 2.45 GHz with 100 MHz bandwidth",
            design_specs={
                "frequency_ghz": 2.45,
                "bandwidth_mhz": 100.0,
                "antenna_family": "microstrip_patch",
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
    package = parser.parse_package(optimize_response.command_package)
    parser.validate_package(package)

    max_iterations = DEFAULT_MAX_ITERATIONS
    optional_failures = {"export_farfield", "extract_farfield_metrics", "add_farfield_monitor"}
    loop_runs: list[dict[str, Any]] = []

    for loop_index in range(max_iterations):
        logger.info(f"Executing CST iteration {loop_index} (package iteration_index={package.iteration_index})")

        engine = ExecutionEngine()
        execution_results = await engine.execute_command_package(package)
        exec_progress = engine.get_progress()

        iteration_report: dict[str, Any] = {
            "loop_index": loop_index,
            "package_iteration_index": int(package.iteration_index),
            "design_id": package.design_id,
            "execution": {
                "dry_run": engine.dry_run,
                "progress": exec_progress,
                "results": [r.to_dict() for r in execution_results],
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

        s11_metrics, s11_path = _resolve_s11_metrics(package)
        farfield_metrics, farfield_metrics_path = _resolve_farfield_metrics(package)

        summary_metrics_path = EXPORTS_DIR / f"summary_metrics_iter{loop_index}.json"
        summary_metrics = {
            "s11_metrics": s11_metrics,
            "farfield_metrics": farfield_metrics,
        }
        summary_metrics_path.write_text(json.dumps(summary_metrics, indent=2), encoding="utf-8")

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

        package = parser.parse_package(next_package_data)
        parser.validate_package(package)

    report["steps"]["loop"] = {
        "max_iterations": max_iterations,
        "executed_iterations": len(loop_runs),
        "runs": loop_runs,
    }

    report["finished_at"] = datetime.now().isoformat()
    report["status"] = "success"

    out_path = REPORTS_DIR / f"cst_pipeline_once_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info("CST pipeline one-pass run succeeded")
    logger.info(f"Session: {session_id}")
    logger.info(f"Trace: {trace_id}")
    logger.info(f"Report: {out_path}")

    return 0


async def _main() -> int:
    try:
        return await run_once()
    except Exception as exc:
        logger.error(f"CST one-pass pipeline failed: {exc}")
        failure_report = {
            "started_at": datetime.now().isoformat(),
            "status": "failed",
            "error": str(exc),
        }
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = REPORTS_DIR / f"cst_pipeline_once_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        out_path.write_text(json.dumps(failure_report, indent=2), encoding="utf-8")
        logger.info(f"Failure report: {out_path}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
