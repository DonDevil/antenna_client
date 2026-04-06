from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
EXPORTS_DIR = ROOT / "artifacts" / "exports"
LOG_FILE = ROOT / "logs" / "antenna_client.log"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _relative(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _extract_latest_ids_from_log() -> tuple[str | None, str | None, str | None]:
    if not LOG_FILE.exists():
        return None, None, None

    text = LOG_FILE.read_text(encoding="utf-8", errors="ignore")
    session_matches = re.findall(r"'session_id':\s*'([^']+)'", text)
    trace_matches = re.findall(r"'trace_id':\s*'([^']+)'", text)
    design_matches = re.findall(r"'design_id':\s*'([^']+)'", text)

    session_id = session_matches[-1] if session_matches else None
    trace_id = trace_matches[-1] if trace_matches else None
    design_id = design_matches[-1] if design_matches else None
    return session_id, trace_id, design_id


def _latest_farfield_metrics() -> tuple[Path | None, dict[str, Any] | None]:
    if not EXPORTS_DIR.exists():
        return None, None
    candidates = sorted(
        [p for p in EXPORTS_DIR.glob("*_metrics.json") if p.name != "summary_metrics.json"],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        data = _load_json(candidate)
        if not data:
            continue
        if "main_lobe_direction_deg" in data or "beamwidth_3db_deg" in data:
            return candidate, data
    return None, None


def build_payload(
    session_id: str | None,
    trace_id: str | None,
    design_id: str | None,
    iteration_index: int,
    fallback_vswr: float,
) -> dict[str, Any]:
    sparam_metrics_path = EXPORTS_DIR / "summary_metrics.json"
    sparam_metrics = _load_json(sparam_metrics_path)

    farfield_metrics_path, farfield_metrics = _latest_farfield_metrics()

    actual_center_frequency_ghz = float(sparam_metrics.get("center_frequency", 2.4) if sparam_metrics else 2.4)
    actual_bandwidth_mhz = float((sparam_metrics.get("bandwidth", 0.0) * 1000.0) if sparam_metrics else 0.0)
    actual_return_loss_db = float(sparam_metrics.get("min_s11_db", -18.0) if sparam_metrics else -18.0)

    parsed_gain = None
    if farfield_metrics:
        parsed_gain = (
            farfield_metrics.get("max_realized_gain_dbi")
            or farfield_metrics.get("max_gain_dbi")
            or farfield_metrics.get("theta_cut_peak_gain_dbi")
        )
    actual_gain_dbi = float(parsed_gain if parsed_gain is not None else 0.0)

    payload = {
        "schema_version": "client_feedback.v1",
        "session_id": session_id or "PENDING_SESSION_ID",
        "trace_id": trace_id or "PENDING_TRACE_ID",
        "design_id": design_id or "PENDING_DESIGN_ID",
        "iteration_index": int(iteration_index),
        "simulation_status": "completed",
        "actual_center_frequency_ghz": actual_center_frequency_ghz,
        "actual_bandwidth_mhz": actual_bandwidth_mhz,
        "actual_return_loss_db": actual_return_loss_db,
        "actual_vswr": float(fallback_vswr),
        "actual_gain_dbi": actual_gain_dbi,
        "artifacts": {
            "s11_trace_ref": f"artifacts/s11_iter{iteration_index}.json",
            "summary_metrics_ref": (
                _relative(sparam_metrics_path)
                if sparam_metrics_path.exists()
                else f"artifacts/summary_iter{iteration_index}.json"
            ),
            "farfield_ref": _relative(farfield_metrics_path) if farfield_metrics_path else None,
            "current_distribution_ref": None,
        },
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare offline client_feedback payload from local CST artifacts.")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--trace-id", default=None)
    parser.add_argument("--design-id", default=None)
    parser.add_argument("--iteration-index", type=int, default=0)
    parser.add_argument("--vswr", type=float, default=2.0)
    args = parser.parse_args()

    inferred_session, inferred_trace, inferred_design = _extract_latest_ids_from_log()
    session_id = args.session_id or inferred_session
    trace_id = args.trace_id or inferred_trace
    design_id = args.design_id or inferred_design

    payload = build_payload(
        session_id=session_id,
        trace_id=trace_id,
        design_id=design_id,
        iteration_index=args.iteration_index,
        fallback_vswr=args.vswr,
    )

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = EXPORTS_DIR / f"pending_feedback_{timestamp}.json"
    latest_path = EXPORTS_DIR / "pending_feedback_latest.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Wrote offline feedback payload: {out_path}")
    print(f"Updated latest payload file: {latest_path}")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
