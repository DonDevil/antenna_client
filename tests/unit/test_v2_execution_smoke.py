import pytest

import executor.execution_engine as execution_engine_module
from executor.command_parser import CommandParser


class FakeCSTApp:
    def connect(self):
        return True

    def execute_macro(self, macro_code):
        return True

    def rebuild_model(self, full_history=False):
        return True

    def set_parameter(self, name, value, description=None, create_only=False):
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
            {"seq": 1, "command": "create_component", "params": {"component": "antenna"}},
            {"seq": 2, "command": "define_parameter", "params": {"name": "px", "value": 37}},
            {
                "seq": 3,
                "command": "define_brick",
                "params": {
                    "name": "solid1",
                    "component": "antenna",
                    "material": "PEC",
                    "xrange": ["-px/2", "px/2"],
                    "yrange": [-5, 5],
                    "zrange": [0, 1],
                },
            },
            {
                "seq": 4,
                "command": "define_extrude",
                "params": {
                    "name": "extrude1",
                    "component": "antenna",
                    "material": "PEC",
                    "points": [[0, 0], [10, 0], [10, 5]],
                },
            },
            {
                "seq": 5,
                "command": "boolean_add",
                "params": {"component": "antenna", "target": "solid1", "tool": "extrude1"},
            },
            {
                "seq": 6,
                "command": "pick_face",
                "params": {"component": "antenna", "solid": "solid1", "face_id": 1},
            },
            {
                "seq": 7,
                "command": "update_parameter",
                "params": {"name": "px", "value": 41.5},
            },
            {
                "seq": 8,
                "command": "rebuild_model",
                "params": {},
            },
            {
                "seq": 9,
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

    assert len(results) == 9
    assert all(result.success for result in results)

    vba_dir = tmp_path / "artifacts" / "vba"
    assert (vba_dir / "01_create_component.bas").exists()
    assert (vba_dir / "02_define_parameter.bas").exists()
    assert (vba_dir / "03_define_brick.bas").exists()
    assert (vba_dir / "04_define_extrude.bas").exists()
    assert (vba_dir / "05_boolean_add.bas").exists()
    assert (vba_dir / "06_pick_face.bas").exists()
    assert (vba_dir / "07_update_parameter.bas").exists()
    assert (vba_dir / "08_rebuild_model.bas").exists()
    assert (vba_dir / "09_calculate_port_extension_coefficient.bas").exists()
