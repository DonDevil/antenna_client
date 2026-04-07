import pytest

import executor.execution_engine as execution_engine_module
from executor.command_parser import CommandParser


class FakeCSTApp:
    def connect(self):
        return True

    def execute_macro(self, macro_code):
        return True


@pytest.mark.asyncio
async def test_v2_package_exec_generates_expected_vba_files(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(execution_engine_module, "CSTApp", FakeCSTApp)

    parser = CommandParser()
    payload = {
        "schema_version": "cst_command_package.v2",
        "command_catalog_version": "v2",
        "session_id": "sess-v2",
        "trace_id": "trace-v2",
        "design_id": "design-v2",
        "iteration_index": 0,
        "units": {"geometry": "mm", "frequency": "ghz"},
        "predicted_dimensions": {},
        "predicted_metrics": {},
        "commands": [
            {"seq": 1, "command": "create_component", "params": {"component": "component1"}},
            {
                "seq": 2,
                "command": "define_brick",
                "params": {
                    "name": "solid1",
                    "component": "component1",
                    "material": "PEC",
                    "xrange": [-10, 10],
                    "yrange": [-5, 5],
                    "zrange": [0, 1],
                },
            },
            {
                "seq": 3,
                "command": "define_extrude",
                "params": {
                    "name": "extrude1",
                    "component": "component1",
                    "material": "PEC",
                    "points": [[0, 0], [10, 0], [10, 5]],
                },
            },
            {
                "seq": 4,
                "command": "boolean_add",
                "params": {"component": "component1", "target": "solid1", "tool": "extrude1"},
            },
            {
                "seq": 5,
                "command": "pick_face",
                "params": {"component": "component1", "solid": "solid1", "face_id": 1},
            },
            {
                "seq": 6,
                "command": "calculate_port_extension_coefficient",
                "params": {"port_id": 1},
            },
        ],
        "expected_exports": [],
        "safety_checks": ["command_order_validated"],
    }

    package = parser.parse_package(payload)
    assert parser.validate_package(package) is True

    engine = execution_engine_module.ExecutionEngine()
    results = await engine.execute_command_package(package)

    assert len(results) == 6
    assert all(result.success for result in results)

    vba_dir = tmp_path / "artifacts" / "vba"
    assert (vba_dir / "01_create_component.bas").exists()
    assert (vba_dir / "02_define_brick.bas").exists()
    assert (vba_dir / "03_define_extrude.bas").exists()
    assert (vba_dir / "04_boolean_add.bas").exists()
    assert (vba_dir / "05_pick_face.bas").exists()
    assert (vba_dir / "06_calculate_port_extension_coefficient.bas").exists()
