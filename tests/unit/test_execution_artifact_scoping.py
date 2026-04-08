import asyncio
import json
from pathlib import Path

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


class GeometryCaptureCSTApp:
    def __init__(self):
        self.macros: list[str] = []

    def connect(self):
        return True

    def execute_macro(self, macro_code):
        self.macros.append(macro_code)
        return True


def test_execution_engine_scopes_export_hints_by_session(monkeypatch, tmp_path):
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
    results = asyncio.run(engine.execute_command_package(package))

    assert all(result.success for result in results)

    artifacts = engine.get_artifacts()
    s11_hint = artifacts.get("s11_destination_hint", "")
    farfield_hint = artifacts.get("farfield_destination_hint", "")
    assert s11_hint.startswith("session-abc-123_iter3_design_xyz_")
    assert farfield_hint.startswith("session-abc-123_iter3_design_xyz_")
    assert artifacts["s11_trace_path"].endswith(f"{s11_hint}.txt")
    assert artifacts["summary_metrics_path"].endswith(f"{s11_hint}_summary_metrics.json")
    assert artifacts["farfield_metrics_path"].endswith(f"{farfield_hint}_metrics.json")


def test_execution_engine_derives_feedline_and_port_geometry(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(execution_engine_module, "CSTApp", GeometryCaptureCSTApp)

    parser = CommandParser()
    package = parser.parse_package(
        {
            "schema_version": "cst_command_package.v1",
            "command_catalog_version": "v1",
            "session_id": "session-geom-001",
            "trace_id": "trace-geom-001",
            "design_id": "design-geom-001",
            "iteration_index": 0,
            "units": {"geometry": "mm", "frequency": "ghz"},
            "predicted_dimensions": {},
            "commands": [
                {
                    "seq": 1,
                    "command": "create_substrate",
                    "params": {
                        "name": "substrate",
                        "component": "antenna",
                        "material": "FR-4 (lossy)",
                        "length_mm": 40.0,
                        "width_mm": 50.0,
                        "height_mm": 1.6,
                        "origin_mm": {"x": 0.0, "y": 0.0, "z": 0.0},
                    },
                    "on_failure": "abort",
                    "checksum_scope": "geometry",
                },
                {
                    "seq": 2,
                    "command": "create_ground_plane",
                    "params": {
                        "name": "ground",
                        "component": "antenna",
                        "material": "Copper (annealed)",
                        "length_mm": 40.0,
                        "width_mm": 50.0,
                        "thickness_mm": 0.035,
                        "z_mm": 0.0,
                    },
                    "on_failure": "abort",
                    "checksum_scope": "geometry",
                },
                {
                    "seq": 3,
                    "command": "create_patch",
                    "params": {
                        "name": "patch",
                        "component": "antenna",
                        "material": "Copper (annealed)",
                        "length_mm": 20.0,
                        "width_mm": 30.0,
                        "thickness_mm": 0.035,
                        "center_mm": {"x": 0.0, "y": 0.0, "z": 1.6},
                    },
                    "on_failure": "abort",
                    "checksum_scope": "geometry",
                },
                {
                    "seq": 4,
                    "command": "create_feedline",
                    "params": {
                        "name": "feed",
                        "component": "antenna",
                        "material": "Copper (annealed)",
                        "length_mm": 8.0,
                        "width_mm": 2.0,
                        "thickness_mm": 0.035,
                        "start_mm": {"x": 0.0, "y": -3.0, "z": 1.6},
                        "end_mm": {"x": 0.0, "y": -11.0, "z": 1.6},
                    },
                    "on_failure": "abort",
                    "checksum_scope": "geometry",
                },
                {
                    "seq": 5,
                    "command": "create_port",
                    "params": {
                        "port_id": 1,
                        "impedance_ohm": 50.0,
                        "reference_mm": {"x": 0.0, "y": 0.0, "z": 0.0},
                    },
                    "on_failure": "abort",
                    "checksum_scope": "simulation",
                },
            ],
            "expected_exports": [],
            "safety_checks": [],
        }
    )

    engine = execution_engine_module.ExecutionEngine()
    results = asyncio.run(engine.execute_command_package(package))

    assert all(result.success for result in results)
    assert len(engine.cst_app.macros) == 5

    patch_macro = engine.cst_app.macros[2]
    feed_macro = engine.cst_app.macros[3]
    port_macro = engine.cst_app.macros[4]

    assert '.Xrange "-15.0", "15.0"' in patch_macro
    assert '.Yrange "-10.0", "10.0"' in patch_macro
    assert '.Xrange "-1.0", "1.0"' in feed_macro
    assert '.Yrange "-20.0", "-10.0"' in feed_macro
    assert '.SetP1 "False", "0.0", "-20.0", "1.6"' in port_macro
    assert '.SetP2 "False", "0.0", "-20.0", "0.035"' in port_macro
    assert 'CalculatePortExtensionCoefficient' not in port_macro


def test_execution_engine_derives_define_brick_feed_and_port_geometry(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(execution_engine_module, "CSTApp", GeometryCaptureCSTApp)

    parser = CommandParser()
    package = parser.parse_package(
        {
            "schema_version": "cst_command_package.v1",
            "command_catalog_version": "v1",
            "session_id": "session-brick-001",
            "trace_id": "trace-brick-001",
            "design_id": "design-brick-001",
            "iteration_index": 0,
            "units": {"geometry": "mm", "frequency": "ghz"},
            "predicted_dimensions": {},
            "commands": [
                {
                    "seq": 1,
                    "command": "define_brick",
                    "params": {
                        "name": "substrate",
                        "component": "antenna",
                        "material": "FR-4 (lossy)",
                        "xrange": [-25.0, 25.0],
                        "yrange": [-20.0, 20.0],
                        "zrange": [0.0, 1.6],
                    },
                    "on_failure": "abort",
                    "checksum_scope": "geometry",
                },
                {
                    "seq": 2,
                    "command": "define_brick",
                    "params": {
                        "name": "ground",
                        "component": "antenna",
                        "material": "Copper (annealed)",
                        "xrange": [-25.0, 25.0],
                        "yrange": [-20.0, 20.0],
                        "zrange": [0.0, 0.035],
                    },
                    "on_failure": "abort",
                    "checksum_scope": "geometry",
                },
                {
                    "seq": 3,
                    "command": "define_brick",
                    "params": {
                        "name": "patch",
                        "component": "antenna",
                        "material": "Copper (annealed)",
                        "xrange": [-15.0, 15.0],
                        "yrange": [-10.0, 10.0],
                        "zrange": [1.6, 1.635],
                    },
                    "on_failure": "abort",
                    "checksum_scope": "geometry",
                },
                {
                    "seq": 4,
                    "command": "define_brick",
                    "params": {
                        "name": "feed",
                        "component": "antenna",
                        "material": "Copper (annealed)",
                        "xrange": [-1.0, 1.0],
                        "yrange": [-11.0, -5.0],
                        "zrange": [1.6, 1.635],
                    },
                    "on_failure": "abort",
                    "checksum_scope": "geometry",
                },
                {
                    "seq": 5,
                    "command": "create_port",
                    "params": {
                        "port_id": 1,
                        "impedance_ohm": 50.0,
                        "reference_mm": {"x": 0.0, "y": 0.0, "z": 0.0},
                    },
                    "on_failure": "abort",
                    "checksum_scope": "simulation",
                },
            ],
            "expected_exports": [],
            "safety_checks": [],
        }
    )

    engine = execution_engine_module.ExecutionEngine()
    results = asyncio.run(engine.execute_command_package(package))

    assert all(result.success for result in results)
    assert len(engine.cst_app.macros) == 5

    feed_macro = engine.cst_app.macros[3]
    port_macro = engine.cst_app.macros[4]

    assert '.Yrange "-20.0", "-10.0"' in feed_macro
    assert '.SetP1 "False", "0.0", "-20.0", "1.6"' in port_macro
    assert '.SetP2 "False", "0.0", "-20.0", "0.035"' in port_macro
    assert 'CalculatePortExtensionCoefficient' not in port_macro


def test_execution_engine_derives_symbolic_define_brick_feed_and_port_geometry(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(execution_engine_module, "CSTApp", GeometryCaptureCSTApp)

    parser = CommandParser()
    package = parser.parse_package(
        {
            "schema_version": "cst_command_package.v1",
            "command_catalog_version": "v1",
            "session_id": "session-sym-001",
            "trace_id": "trace-sym-001",
            "design_id": "design-sym-001",
            "iteration_index": 0,
            "units": {"geometry": "mm", "frequency": "ghz"},
            "predicted_dimensions": {},
            "commands": [
                {
                    "seq": 1,
                    "command": "define_brick",
                    "params": {
                        "name": "substrate",
                        "component": "antenna",
                        "material": "Rogers_RT_duroid_5880",
                        "xrange": ["-sx/2", "sx/2"],
                        "yrange": ["-sy/2", "sy/2"],
                        "zrange": ["0.0", "h_sub"],
                    },
                    "on_failure": "abort",
                    "checksum_scope": "geometry",
                },
                {
                    "seq": 2,
                    "command": "define_brick",
                    "params": {
                        "name": "ground",
                        "component": "antenna",
                        "material": "Copper_(annealed)",
                        "xrange": ["-sx/2", "sx/2"],
                        "yrange": ["-sy/2", "sy/2"],
                        "zrange": ["-t_cu", "0.0"],
                    },
                    "on_failure": "abort",
                    "checksum_scope": "geometry",
                },
                {
                    "seq": 3,
                    "command": "define_brick",
                    "params": {
                        "name": "patch",
                        "component": "antenna",
                        "material": "Copper_(annealed)",
                        "xrange": ["-px/2", "px/2"],
                        "yrange": ["-py/2", "py/2"],
                        "zrange": ["h_sub", "h_sub+t_cu"],
                    },
                    "on_failure": "abort",
                    "checksum_scope": "geometry",
                },
                {
                    "seq": 4,
                    "command": "define_brick",
                    "params": {
                        "name": "feed",
                        "component": "antenna",
                        "material": "Copper_(annealed)",
                        "xrange": ["feed_x-(feed_w/2)", "feed_x+(feed_w/2)"],
                        "yrange": ["feed_y-feed_len", "feed_y"],
                        "zrange": ["h_sub", "h_sub+t_cu"],
                    },
                    "on_failure": "abort",
                    "checksum_scope": "geometry",
                },
                {
                    "seq": 5,
                    "command": "create_port",
                    "params": {
                        "port_id": 1,
                        "impedance_ohm": 50.0,
                        "reference_mm": {"x": 0.0, "y": 0.0, "z": 0.0},
                    },
                    "on_failure": "abort",
                    "checksum_scope": "simulation",
                },
            ],
            "expected_exports": [],
            "safety_checks": [],
        }
    )

    engine = execution_engine_module.ExecutionEngine()
    results = asyncio.run(engine.execute_command_package(package))

    assert all(result.success for result in results)
    assert len(engine.cst_app.macros) == 5

    feed_macro = engine.cst_app.macros[3]
    port_macro = engine.cst_app.macros[4]

    assert '.Yrange "-sy/2", "-py/2"' in feed_macro
    assert '.SetP1 "False", "feed_x", "-sy/2", "h_sub"' in port_macro
    assert '.SetP2 "False", "feed_x", "-sy/2", "0.0"' in port_macro
