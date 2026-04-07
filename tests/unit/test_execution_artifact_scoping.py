import json
from pathlib import Path

import pytest

import executor.execution_engine as execution_engine_module
from executor.command_parser import CommandParser


class FakeCSTApp:
    def connect(self):
        return True

    def create_project(self, project_name):
        return str((Path("artifacts") / f"{project_name}.cst").resolve())

    def run_simulation(self, timeout_sec=600):
        return True

    def export_s_parameters(self, destination_hint="s11"):
        path = (Path("artifacts") / "exports" / f"{destination_hint}.txt").resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("2.45 -15.0\n", encoding="utf-8")
        return str(path)

    def extract_summary_metrics(self, sparam_file):
        return {
            "center_frequency": 2.45,
            "bandwidth": 0.1,
            "min_s11_db": -15.0,
        }

    def export_farfield(self, frequency_ghz=2.4, destination_hint="farfield"):
        exports = (Path("artifacts") / "exports").resolve()
        exports.mkdir(parents=True, exist_ok=True)
        source = exports / f"{destination_hint}.txt"
        summary = exports / f"{destination_hint}_summary.txt"
        cut = exports / f"{destination_hint}_theta_cut.txt"
        meta = exports / f"{destination_hint}_meta.json"
        source.write_text("theta phi gain\n", encoding="utf-8")
        summary.write_text("Maximum gain [dB]: 5.0\n", encoding="utf-8")
        cut.write_text("0 0 5.0\n180 0 -6.0\n", encoding="utf-8")
        meta.write_text(json.dumps({"hint": destination_hint}, indent=2), encoding="utf-8")
        return str(source)

    def extract_farfield_metrics(self, destination_hint="farfield"):
        metrics_path = (Path("artifacts") / "exports" / f"{destination_hint}_metrics.json").resolve()
        payload = {
            "main_lobe_direction_deg": 0.0,
            "beamwidth_3db_deg": 50.0,
            "max_realized_gain_dbi": 5.0,
            "metrics_file": str(metrics_path),
        }
        metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload


@pytest.mark.asyncio
async def test_execution_engine_scopes_export_hints_by_session(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(execution_engine_module, "CSTApp", FakeCSTApp)

    parser = CommandParser()
    package = parser.parse_package(
        {
            "schema_version": "cst_command_package.v1",
            "command_catalog_version": "v1",
            "session_id": "session-abc-123",
            "trace_id": "trace-001",
            "design_id": "design_xyz",
            "iteration_index": 3,
            "units": {"length": "mm", "frequency": "ghz"},
            "predicted_dimensions": {},
            "commands": [
                {"seq": 1, "command": "export_s_parameters", "params": {"destination_hint": "s11"}, "on_failure": "abort", "checksum_scope": "none"},
                {"seq": 2, "command": "extract_summary_metrics", "params": {"destination_hint": "s11"}, "on_failure": "abort", "checksum_scope": "none"},
                {"seq": 3, "command": "export_farfield", "params": {"destination_hint": "farfield", "frequency_ghz": 2.45}, "on_failure": "abort", "checksum_scope": "none"},
                {"seq": 4, "command": "extract_farfield_metrics", "params": {"destination_hint": "farfield"}, "on_failure": "abort", "checksum_scope": "none"},
            ],
            "expected_exports": [],
            "safety_checks": [],
        }
    )

    engine = execution_engine_module.ExecutionEngine()
    results = await engine.execute_command_package(package)

    assert all(result.success for result in results)

    artifacts = engine.get_artifacts()
    s11_hint = artifacts.get("s11_destination_hint", "")
    farfield_hint = artifacts.get("farfield_destination_hint", "")
    assert s11_hint.startswith("session-abc-123_iter3_design_xyz_")
    assert farfield_hint.startswith("session-abc-123_iter3_design_xyz_")
    assert artifacts["s11_trace_path"].endswith(f"{s11_hint}.txt")
    assert artifacts["summary_metrics_path"].endswith(f"{s11_hint}_summary_metrics.json")
    assert artifacts["farfield_metrics_path"].endswith(f"{farfield_hint}_metrics.json")
