#!/usr/bin/env python3
"""Run randomized CST-backed single-cycle optimize/execute/feedback loops overnight.

Each cycle performs exactly one command-package execution round:
1) Send optimize request with randomized target parameters.
2) Execute returned command package in CST.
3) Send one feedback payload to the server.
4) Close/disconnect CST, then force-close CST processes before next cycle.

This script is intended for unattended overnight runs with robust error handling,
cycle-level reporting, and an aggregate report.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, TypeVar

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from comm.api_client import ApiClient
from comm.request_builder import RequestBuilder
from comm.server_connector import ServerConnector
from executor.command_parser import CommandParser
from executor.execution_engine import ExecutionEngine
from utils.logger import get_logger

logger = get_logger(__name__)

CONFIG_PATH = PROJECT_ROOT / "config.json"
REPORTS_DIR = PROJECT_ROOT / "artifacts" / "reports"
EXPORTS_DIR = PROJECT_ROOT / "artifacts" / "exports"

OPTIONAL_FAILURES = {"export_farfield", "extract_farfield_metrics", "add_farfield_monitor"}
T = TypeVar("T")


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Failed to load config.json: {exc}")
        return {}


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


def _resolve_metrics_from_execution_artifacts(
    artifacts: dict[str, Any],
) -> tuple[Optional[dict[str, Any]], Optional[Path], Optional[dict[str, Any]], Optional[Path]]:
    from cst_client.cst_app import CSTApp

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


def _build_feedback_payload(
    *,
    package: Any,
    session_id: str,
    trace_id: str,
    design_id: str,
    s11_metrics: Optional[dict[str, Any]],
    s11_path: Optional[Path],
    farfield_metrics: Optional[dict[str, Any]],
    farfield_metrics_path: Optional[Path],
    note: str,
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

    return {
        "schema_version": "client_feedback.v1",
        "session_id": session_id,
        "trace_id": trace_id,
        "design_id": design_id,
        "iteration_index": int(getattr(package, "iteration_index", 0)),
        "simulation_status": "completed",
        "actual_center_frequency_ghz": round(center_frequency_ghz, 6),
        "actual_bandwidth_mhz": round(bandwidth_ghz * 1000.0, 3),
        "actual_return_loss_db": round(return_loss_db, 3),
        "actual_vswr": round(vswr, 4),
        "actual_gain_dbi": round(gain_dbi, 3),
        "notes": note,
        "artifacts": {
            "s11_trace_ref": str(s11_path.resolve()) if s11_path else None,
            "summary_metrics_ref": str((EXPORTS_DIR / "summary_metrics.json").resolve()),
            "farfield_ref": str(farfield_metrics_path.resolve()) if farfield_metrics_path else None,
            "current_distribution_ref": None,
        },
    }


@dataclass(frozen=True)
class RandomSpec:
    frequency_ghz: float
    bandwidth_mhz: float
    max_vswr: float
    min_gain_dbi: float
    min_return_loss_db: float



@dataclass(frozen=True)
class RandomRanges:
    frequency_min_ghz: float = 2.2
    frequency_max_ghz: float = 3.2
    bandwidth_min_mhz: float = 70.0
    bandwidth_max_mhz: float = 250.0
    max_vswr_min: float = 1.6
    max_vswr_max: float = 2.2
    min_gain_min_dbi: float = 0.0
    min_gain_max_dbi: float = 5.0
    return_loss_min_db: float = 8.0
    return_loss_max_db: float = 18.0

    def validate(self) -> None:
        if self.frequency_min_ghz >= self.frequency_max_ghz:
            raise ValueError("frequency min must be < max")
        if self.bandwidth_min_mhz >= self.bandwidth_max_mhz:
            raise ValueError("bandwidth min must be < max")
        if self.max_vswr_min >= self.max_vswr_max:
            raise ValueError("max_vswr min must be < max")
        if self.min_gain_min_dbi > self.min_gain_max_dbi:
            raise ValueError("min_gain min must be <= max")
        if self.return_loss_min_db <= 0 or self.return_loss_max_db <= 0:
            raise ValueError("return loss range must be positive magnitudes")
        if self.return_loss_min_db > self.return_loss_max_db:
            raise ValueError("return_loss min must be <= max")


def _sample_specs(rng: random.Random, ranges: RandomRanges) -> RandomSpec:
    frequency_ghz = round(rng.uniform(ranges.frequency_min_ghz, ranges.frequency_max_ghz), 4)
    bandwidth_mhz = round(rng.uniform(ranges.bandwidth_min_mhz, ranges.bandwidth_max_mhz), 2)
    max_vswr = round(rng.uniform(ranges.max_vswr_min, ranges.max_vswr_max), 3)
    min_gain_dbi = round(rng.uniform(ranges.min_gain_min_dbi, ranges.min_gain_max_dbi), 3)
    min_return_loss_db = -round(rng.uniform(ranges.return_loss_min_db, ranges.return_loss_max_db), 3)
    return RandomSpec(
        frequency_ghz=frequency_ghz,
        bandwidth_mhz=bandwidth_mhz,
        max_vswr=max_vswr,
        min_gain_dbi=min_gain_dbi,
        min_return_loss_db=min_return_loss_db,
    )


def _build_random_request(rng: random.Random, ranges: RandomRanges) -> tuple[dict[str, Any], str, dict[str, Any]]:
    sampled = _sample_specs(rng, ranges)
    design_specs = {
        "frequency_ghz": sampled.frequency_ghz,
        "bandwidth_mhz": sampled.bandwidth_mhz,
        "antenna_family": "microstrip_patch",
        "patch_shape": "rectangular",
        "feed_type": "edge",
        "polarization": "linear",
        "constraints": {
            "max_vswr": sampled.max_vswr,
            "target_gain_dbi": sampled.min_gain_dbi,
            "minimum_return_loss_db": sampled.min_return_loss_db,
        },
    }
    user_text = (
        "Design a microstrip patch antenna with "
        f"center frequency {sampled.frequency_ghz} GHz and "
        f"bandwidth {sampled.bandwidth_mhz} MHz."
    )
    request = RequestBuilder().build_optimize_request(
        user_text=user_text,
        design_specs=design_specs,
    )
    return request.model_dump(), user_text, design_specs


def _find_latest_aggregate_report() -> Optional[Path]:
    candidates = sorted(REPORTS_DIR.glob("autotrain_aggregate_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _load_resume_state(resume_file: Optional[Path]) -> tuple[list[dict[str, Any]], int, Optional[str]]:
    source = resume_file if resume_file is not None else _find_latest_aggregate_report()
    if source is None:
        return [], 0, None
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Failed to parse resume file {source}: {exc}") from exc

    results = payload.get("results")
    if not isinstance(results, list):
        raise RuntimeError(f"Resume file {source} is missing a valid 'results' list")
    normalized: list[dict[str, Any]] = []
    for item in results:
        if isinstance(item, dict):
            normalized.append(item)
    return normalized, len(normalized), str(source.resolve())


def _advance_rng_for_completed_cycles(rng: random.Random, completed_cycles: int, ranges: RandomRanges) -> None:
    # Keep deterministic continuation when --seed is used together with resume.
    for _ in range(max(0, completed_cycles)):
        _sample_specs(rng, ranges)


async def _with_retries(
    operation_name: str,
    factory: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    delay_sec: float,
) -> T:
    last_exc: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            return await factory()
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            logger.warning(
                "%s failed on attempt %s/%s: %s. Retrying in %.1f sec.",
                operation_name,
                attempt,
                attempts,
                exc,
                delay_sec,
            )
            await asyncio.sleep(max(0.0, delay_sec))
    if last_exc is None:
        raise RuntimeError(f"{operation_name} failed without exception details")
    raise RuntimeError(f"{operation_name} failed after {attempts} attempts: {last_exc}") from last_exc


def _force_close_cst_processes() -> dict[str, Any]:
    process_names = [
        "CST DESIGN ENVIRONMENT.exe",
        "CSTStudio.exe",
        "CST Studio.exe",
    ]
    kills: list[dict[str, Any]] = []
    for proc in process_names:
        try:
            completed = subprocess.run(
                ["taskkill", "/F", "/IM", proc],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            kills.append(
                {
                    "process": proc,
                    "returncode": completed.returncode,
                    "stdout": (completed.stdout or "").strip(),
                    "stderr": (completed.stderr or "").strip(),
                }
            )
        except Exception as exc:
            kills.append({"process": proc, "error": str(exc)})
    return {"killed": kills}


async def _run_one_cycle(
    *,
    cycle_index: int,
    base_url: str,
    timeout_sec: int,
    rng: random.Random,
    ranges: RandomRanges,
    retry_attempts: int,
    retry_delay_sec: float,
) -> dict[str, Any]:
    cycle_report: dict[str, Any] = {
        "cycle_index": cycle_index,
        "started_at": datetime.now().isoformat(),
        "server": base_url,
        "status": "running",
    }

    optimize_payload, user_text, design_specs = _build_random_request(rng, ranges)
    cycle_report["request"] = {
        "user_text": user_text,
        "design_specs": design_specs,
    }

    parser = CommandParser()
    engine: ExecutionEngine | None = None

    try:
        connector = ServerConnector(base_url, timeout_sec=timeout_sec)
        async with connector:
            api = ApiClient(connector)

            health = await _with_retries(
                "health_check",
                lambda: api.health_check(),
                attempts=retry_attempts,
                delay_sec=retry_delay_sec,
            )
            cycle_report["health"] = health
            if health.get("status") != "ok":
                raise RuntimeError(f"Server health is not ok: {health}")

            optimize_response = await _with_retries(
                "optimize",
                lambda: api.optimize(optimize_payload),
                attempts=retry_attempts,
                delay_sec=retry_delay_sec,
            )

        if optimize_response.status not in ("accepted", "completed"):
            raise RuntimeError(f"Unexpected optimize status: {optimize_response.status}")
        if not optimize_response.command_package:
            raise RuntimeError("Optimize response did not include command_package")

        session_id = optimize_response.session_id or ""
        trace_id = optimize_response.trace_id or ""
        design_id = str(optimize_response.command_package.get("design_id") or "")
        if not session_id or not trace_id or not design_id:
            raise RuntimeError("Missing session_id, trace_id, or design_id in optimize response")

        package = parser.parse_package(optimize_response.command_package)
        parser.validate_package(package)

        engine = ExecutionEngine()
        execution_results = await engine.execute_command_package(package)
        execution_artifacts = engine.get_artifacts()
        progress = engine.get_progress()

        cycle_report["execution"] = {
            "dry_run": engine.dry_run,
            "progress": progress,
            "results": [r.to_dict() for r in execution_results],
            "artifacts": execution_artifacts,
        }

        if engine.dry_run:
            raise RuntimeError("Execution ran in dry-run mode. Ensure CST is installed and reachable.")

        failed_results = [r for r in execution_results if not r.success]
        non_optional_failed = []
        for failed in failed_results:
            command_name = str(failed.command_id).split(":", 1)[-1]
            if command_name not in OPTIONAL_FAILURES:
                non_optional_failed.append(failed)
        if non_optional_failed:
            failed_ids = ", ".join(r.command_id for r in non_optional_failed)
            raise RuntimeError(f"Non-optional command failures: {failed_ids}")

        s11_metrics, s11_path, farfield_metrics, farfield_metrics_path = _resolve_metrics_from_execution_artifacts(
            execution_artifacts
        )
        if not s11_path:
            raise RuntimeError("Missing s11_trace_path in execution artifacts")

        summary_metrics_path = EXPORTS_DIR / f"autotrain_summary_cycle_{cycle_index}.json"
        summary_metrics_path.write_text(
            json.dumps(
                {
                    "cycle_index": cycle_index,
                    "s11_metrics": s11_metrics,
                    "farfield_metrics": farfield_metrics,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        feedback_payload = _build_feedback_payload(
            package=package,
            session_id=session_id,
            trace_id=trace_id,
            design_id=design_id,
            s11_metrics=s11_metrics,
            s11_path=s11_path,
            farfield_metrics=farfield_metrics,
            farfield_metrics_path=farfield_metrics_path,
            note="Autotrain single-cycle run.",
        )
        feedback_payload["artifacts"]["summary_metrics_ref"] = str(summary_metrics_path.resolve())

        connector_result = ServerConnector(base_url, timeout_sec=timeout_sec)
        async with connector_result:
            api_result = ApiClient(connector_result)
            feedback_response = await _with_retries(
                "send_result",
                lambda: api_result.send_result(feedback_payload),
                attempts=retry_attempts,
                delay_sec=retry_delay_sec,
            )

        cycle_report["feedback"] = {
            "request": feedback_payload,
            "response": feedback_response,
        }
        cycle_report["status"] = "success"
        cycle_report["finished_at"] = datetime.now().isoformat()
        return cycle_report
    finally:
        if engine is not None:
            try:
                engine.cst_app.close_project(save=False)
            except Exception:
                pass
            try:
                engine.cst_app.disconnect()
            except Exception:
                pass
        cycle_report.setdefault("teardown", {})
        cycle_report["teardown"]["taskkill"] = _force_close_cst_processes()


async def _dry_validate(*, base_url: str, timeout_sec: int) -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    validation_report: dict[str, Any] = {
        "started_at": datetime.now().isoformat(),
        "server": base_url,
        "checks": {},
    }

    config = _load_config()
    validation_report["checks"]["config_loaded"] = {
        "ok": isinstance(config, dict),
        "path": str(CONFIG_PATH.resolve()),
    }
    validation_report["checks"]["reports_dir"] = {
        "ok": REPORTS_DIR.exists(),
        "path": str(REPORTS_DIR.resolve()),
    }
    validation_report["checks"]["exports_dir"] = {
        "ok": EXPORTS_DIR.exists(),
        "path": str(EXPORTS_DIR.resolve()),
    }

    server_ok = False
    server_payload: dict[str, Any] = {}
    try:
        connector = ServerConnector(base_url, timeout_sec=timeout_sec)
        async with connector:
            api = ApiClient(connector)
            server_payload = await api.health_check()
            server_ok = server_payload.get("status") == "ok"
    except Exception as exc:
        server_payload = {"error": str(exc)}

    validation_report["checks"]["server_health"] = {
        "ok": server_ok,
        "payload": server_payload,
    }

    validation_report["finished_at"] = datetime.now().isoformat()
    validation_report["status"] = "ok" if server_ok else "failed"

    out_path = REPORTS_DIR / f"autotrain_dry_validate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(validation_report, indent=2), encoding="utf-8")

    if server_ok:
        logger.info("Dry validation succeeded. Report: %s", out_path)
        return 0

    logger.error("Dry validation failed. Report: %s", out_path)
    return 1


async def run_autotrain(
    *,
    cycles: int,
    seed: Optional[int],
    wait_between_sec: float,
    stop_on_error: bool,
    retry_attempts: int,
    retry_delay_sec: float,
    ranges: RandomRanges,
    resume_from_latest: bool,
    resume_file: Optional[Path],
) -> int:
    config = _load_config()
    server_cfg = config.get("server", {})
    base_url = str(server_cfg.get("base_url", "http://192.168.29.147:8000"))
    timeout_sec = int(server_cfg.get("timeout_sec", 120))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)

    previous_results: list[dict[str, Any]] = []
    start_idx = 0
    resume_source: Optional[str] = None
    if resume_from_latest or resume_file is not None:
        previous_results, start_idx, resume_source = _load_resume_state(resume_file)
        if seed is not None and start_idx > 0:
            _advance_rng_for_completed_cycles(rng, start_idx, ranges)

    if start_idx >= cycles:
        logger.info("Resume file already has %s results; requested cycles=%s. Nothing to run.", start_idx, cycles)
        return 0

    aggregate: dict[str, Any] = {
        "started_at": datetime.now().isoformat(),
        "server": base_url,
        "cycles_requested": cycles,
        "cycle_start_index": start_idx,
        "seed": seed,
        "wait_between_sec": wait_between_sec,
        "retry_attempts": retry_attempts,
        "retry_delay_sec": retry_delay_sec,
        "stop_on_error": stop_on_error,
        "resume_source": resume_source,
        "random_ranges": {
            "frequency_min_ghz": ranges.frequency_min_ghz,
            "frequency_max_ghz": ranges.frequency_max_ghz,
            "bandwidth_min_mhz": ranges.bandwidth_min_mhz,
            "bandwidth_max_mhz": ranges.bandwidth_max_mhz,
            "max_vswr_min": ranges.max_vswr_min,
            "max_vswr_max": ranges.max_vswr_max,
            "min_gain_min_dbi": ranges.min_gain_min_dbi,
            "min_gain_max_dbi": ranges.min_gain_max_dbi,
            "return_loss_min_db": ranges.return_loss_min_db,
            "return_loss_max_db": ranges.return_loss_max_db,
        },
        "results": list(previous_results),
    }

    failures = sum(1 for item in previous_results if item.get("status") == "failed")
    for idx in range(start_idx, cycles):
        logger.info("Starting autotrain cycle %s/%s", idx + 1, cycles)
        try:
            result = await _run_one_cycle(
                cycle_index=idx,
                base_url=base_url,
                timeout_sec=timeout_sec,
                rng=rng,
                ranges=ranges,
                retry_attempts=retry_attempts,
                retry_delay_sec=retry_delay_sec,
            )
            aggregate["results"].append(result)
            cycle_path = REPORTS_DIR / f"autotrain_cycle_{idx}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            cycle_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            logger.info("Cycle %s finished: %s", idx, cycle_path)
        except Exception as exc:
            failures += 1
            error_result = {
                "cycle_index": idx,
                "started_at": datetime.now().isoformat(),
                "finished_at": datetime.now().isoformat(),
                "status": "failed",
                "error": str(exc),
            }
            aggregate["results"].append(error_result)
            cycle_path = REPORTS_DIR / f"autotrain_cycle_{idx}_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            cycle_path.write_text(json.dumps(error_result, indent=2), encoding="utf-8")
            logger.exception("Cycle %s failed", idx)
            if stop_on_error:
                logger.error("Stopping early due to --stop-on-error")
                break
        if idx < cycles - 1 and wait_between_sec > 0:
            time.sleep(wait_between_sec)

    aggregate["finished_at"] = datetime.now().isoformat()
    aggregate["cycles_completed"] = len(aggregate["results"])
    aggregate["failures"] = failures
    aggregate["status"] = "success" if failures == 0 else "partial_failure"

    out_path = REPORTS_DIR / f"autotrain_aggregate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    logger.info("Autotrain finished. Aggregate report: %s", out_path)

    return 0 if failures == 0 else 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run randomized overnight CST one-cycle optimize/execute/feedback loops.",
    )
    parser.add_argument("--cycles", type=int, default=20, help="Number of single-cycle runs to execute.")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducibility.")
    parser.add_argument("--freq-min-ghz", type=float, default=2.2, help="Random frequency lower bound (GHz).")
    parser.add_argument("--freq-max-ghz", type=float, default=3.2, help="Random frequency upper bound (GHz).")
    parser.add_argument("--bw-min-mhz", type=float, default=70.0, help="Random bandwidth lower bound (MHz).")
    parser.add_argument("--bw-max-mhz", type=float, default=250.0, help="Random bandwidth upper bound (MHz).")
    parser.add_argument("--vswr-min", type=float, default=1.6, help="Random max-VSWR lower bound.")
    parser.add_argument("--vswr-max", type=float, default=2.2, help="Random max-VSWR upper bound.")
    parser.add_argument("--gain-min-dbi", type=float, default=0.0, help="Random minimum-gain lower bound (dBi).")
    parser.add_argument("--gain-max-dbi", type=float, default=5.0, help="Random minimum-gain upper bound (dBi).")
    parser.add_argument(
        "--return-loss-min-db",
        type=float,
        default=8.0,
        help="Random return-loss magnitude lower bound in dB (stored as negative).",
    )
    parser.add_argument(
        "--return-loss-max-db",
        type=float,
        default=18.0,
        help="Random return-loss magnitude upper bound in dB (stored as negative).",
    )
    parser.add_argument(
        "--wait-between-sec",
        type=float,
        default=2.0,
        help="Wait time between cycles to allow clean restart.",
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=3,
        help="Retry attempts for optimize/result/health requests.",
    )
    parser.add_argument(
        "--retry-delay-sec",
        type=float,
        default=2.0,
        help="Delay between retry attempts.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop immediately on first cycle error.",
    )
    parser.add_argument(
        "--resume-from-latest",
        action="store_true",
        help="Resume from the latest autotrain_aggregate report in artifacts/reports.",
    )
    parser.add_argument(
        "--resume-file",
        type=str,
        default=None,
        help="Optional path to a specific aggregate report JSON to resume from.",
    )
    parser.add_argument(
        "--dry-validate",
        action="store_true",
        help="Validate config, output dirs, and server health without running cycles.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.cycles <= 0:
        raise SystemExit("--cycles must be > 0")
    if args.retry_attempts <= 0:
        raise SystemExit("--retry-attempts must be > 0")

    ranges = RandomRanges(
        frequency_min_ghz=args.freq_min_ghz,
        frequency_max_ghz=args.freq_max_ghz,
        bandwidth_min_mhz=args.bw_min_mhz,
        bandwidth_max_mhz=args.bw_max_mhz,
        max_vswr_min=args.vswr_min,
        max_vswr_max=args.vswr_max,
        min_gain_min_dbi=args.gain_min_dbi,
        min_gain_max_dbi=args.gain_max_dbi,
        return_loss_min_db=args.return_loss_min_db,
        return_loss_max_db=args.return_loss_max_db,
    )
    try:
        ranges.validate()
    except ValueError as exc:
        raise SystemExit(f"Invalid random range configuration: {exc}") from exc

    resume_file = Path(args.resume_file).expanduser().resolve() if args.resume_file else None
    if resume_file is not None and not resume_file.exists():
        raise SystemExit(f"--resume-file does not exist: {resume_file}")

    config = _load_config()
    server_cfg = config.get("server", {})
    base_url = str(server_cfg.get("base_url", "http://192.168.29.147:8000"))
    timeout_sec = int(server_cfg.get("timeout_sec", 120))

    if args.dry_validate:
        return asyncio.run(_dry_validate(base_url=base_url, timeout_sec=timeout_sec))

    return asyncio.run(
        run_autotrain(
            cycles=args.cycles,
            seed=args.seed,
            wait_between_sec=max(0.0, args.wait_between_sec),
            stop_on_error=bool(args.stop_on_error),
            retry_attempts=args.retry_attempts,
            retry_delay_sec=max(0.0, args.retry_delay_sec),
            ranges=ranges,
            resume_from_latest=bool(args.resume_from_latest),
            resume_file=resume_file,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
