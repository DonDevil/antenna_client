from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config.json"


def _default_base_url() -> str:
    if not CONFIG_PATH.exists():
        return "http://localhost:8000"
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return "http://localhost:8000"
    return str(config.get("server", {}).get("base_url") or "http://localhost:8000")


def _build_request(frequency_ghz: float, bandwidth_mhz: float) -> dict[str, Any]:
    return {
        "schema_version": "optimize_request.v1",
        "user_request": (
            f"Design a rectangular microstrip patch antenna with edge feed and linear polarization "
            f"at {frequency_ghz} GHz with {bandwidth_mhz} MHz bandwidth."
        ),
        "target_spec": {
            "frequency_ghz": frequency_ghz,
            "bandwidth_mhz": bandwidth_mhz,
            "antenna_family": "microstrip_patch",
            "patch_shape": "rectangular",
            "feed_type": "edge",
            "polarization": "linear",
        },
        "design_constraints": {
            "allowed_materials": ["Copper (annealed)"],
            "allowed_substrates": ["Rogers RT/duroid 5880"],
        },
        "optimization_policy": {
            "mode": "auto_iterate",
            "max_iterations": 5,
            "stop_on_first_valid": True,
            "acceptance": {
                "center_tolerance_mhz": 20.0,
                "minimum_bandwidth_mhz": bandwidth_mhz,
                "maximum_vswr": 2.0,
                "minimum_gain_dbi": 4.0,
                "minimum_return_loss_db": -10.0,
            },
            "fallback_behavior": "best_effort",
        },
        "runtime_preferences": {
            "require_explanations": False,
            "persist_artifacts": True,
            "llm_temperature": 0.0,
            "timeout_budget_sec": 300,
            "priority": "normal",
        },
        "client_capabilities": {
            "supports_farfield_export": True,
            "supports_current_distribution_export": False,
            "supports_parameter_sweep": False,
            "max_simulation_timeout_sec": 600,
            "export_formats": ["json", "csv", "txt"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether the server routes a rectangular microstrip request through the rect-patch ANN path.")
    parser.add_argument("--base-url", default=_default_base_url())
    parser.add_argument("--frequency-ghz", type=float, default=2.45)
    parser.add_argument("--bandwidth-mhz", type=float, default=100.0)
    parser.add_argument("--timeout-sec", type=float, default=15.0)
    parser.add_argument("--dump-response", action="store_true")
    args = parser.parse_args()

    request_payload = _build_request(args.frequency_ghz, args.bandwidth_mhz)

    try:
        with httpx.Client(base_url=args.base_url, timeout=args.timeout_sec) as client:
            health = client.get("/api/v1/health")
            health.raise_for_status()
            optimize = client.post("/api/v1/optimize", json=request_payload)
            optimize.raise_for_status()
    except Exception as exc:
        print(f"Server check failed: {exc}")
        return 2

    health_payload = health.json()
    optimize_payload = optimize.json()
    ann_prediction = optimize_payload.get("ann_prediction") or {}
    model_version = ann_prediction.get("ann_model_version")
    optimizer_hint = ann_prediction.get("optimizer_hint")
    returned_patch_shape = ann_prediction.get("patch_shape")

    print(f"Health status: {health_payload.get('status')}")
    print(f"Optimize status: {optimize_payload.get('status')}")
    print(f"Session ID: {optimize_payload.get('session_id')}")
    print(f"ANN model version: {model_version}")
    print(f"Optimizer hint: {optimizer_hint}")
    print(f"Returned patch shape: {returned_patch_shape}")

    model_text = str(model_version or "").lower()
    route_confirmed = returned_patch_shape == "rectangular"
    ann_active = route_confirmed and model_text not in {"", "recipe_cold_start"}

    if route_confirmed:
        print("Rectangular request routing is active.")
    else:
        print("Response did not clearly indicate rectangular routing.")

    if ann_active:
        print("Family ANN appears active for rectangular requests.")
    else:
        print("Family ANN is not active yet (cold-start fallback or missing ANN artifacts).")

    if args.dump_response:
        print(json.dumps(optimize_payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())