import asyncio

import executor.execution_engine as execution_engine_module
from executor.command_parser import CommandParser


class FakeCSTApp:
    def connect(self):
        return True

    def execute_macro(self, macro_code, title=None):
        return True

    def rebuild_model(self, full_history=False):
        return True

    def set_parameter(self, name, value, description=None, create_only=False):
        return True


def test_execute_package_with_implement_amc_uses_server_family_params(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(execution_engine_module, "CSTApp", FakeCSTApp)

    parser = CommandParser()
    payload = {
        "schema_version": "cst_command_package.v2",
        "command_catalog_version": "v2",
        "session_id": "sess-amc",
        "trace_id": "trace-amc",
        "design_id": "design-amc",
        "iteration_index": 0,
        "units": {"geometry": "mm", "frequency": "ghz"},
        "predicted_dimensions": {
            "patch_length_mm": 29.0,
            "patch_width_mm": 37.0,
            "substrate_length_mm": 55.0,
            "substrate_width_mm": 63.0,
            "substrate_height_mm": 3.0,
            "patch_height_mm": 0.035,
        },
        "predicted_metrics": {"center_frequency_ghz": 2.45},
        "design_recipe": {
            "family": "amc_patch",
            "substrate_material": "Rogers RO3003",
            "conductor_material": "Copper (annealed)",
            "family_parameters": {
                "amc_unit_cell_period_mm": 18.0,
                "amc_patch_size_mm": 14.4,
                "amc_gap_mm": 3.6,
                "amc_array_rows": 7,
                "amc_array_cols": 7,
                "amc_air_gap_mm": 4.0,
            },
        },
        "commands": [
            {"seq": 1, "command": "create_component", "params": {"component": "antenna"}},
            {"seq": 2, "command": "define_parameter", "params": {"name": "px", "value": 37.0}},
            {"seq": 3, "command": "define_parameter", "params": {"name": "py", "value": 29.0}},
            {"seq": 4, "command": "define_parameter", "params": {"name": "sx", "value": 63.0}},
            {"seq": 5, "command": "define_parameter", "params": {"name": "sy", "value": 55.0}},
            {"seq": 6, "command": "define_parameter", "params": {"name": "h_sub", "value": 3.0}},
            {"seq": 7, "command": "define_parameter", "params": {"name": "t_cu", "value": 0.035}},
            {
                "seq": 8,
                "command": "implement_amc",
                "params": {"strategy": "server_family_parameters", "component": "amc"},
            },
            {"seq": 9, "command": "rebuild_model", "params": {}},
        ],
        "expected_exports": [],
        "safety_checks": [],
    }

    package = parser.parse_package(payload)
    assert parser.validate_package(package) is True

    engine = execution_engine_module.ExecutionEngine()
    results = asyncio.run(engine.execute_command_package(package))

    assert len(results) == len(payload["commands"])
    assert all(result.success for result in results)

    artifacts = engine.get_artifacts()
    assert artifacts.get("amc_implemented") is True
    assert artifacts.get("amc_impl_strategy") == "server_family_parameters"
    assert artifacts.get("amc_substrate_material") == "Rogers RO3003"
    assert artifacts.get("amc_conductor_material") == "Copper (annealed)"

    implement_result = next(r for r in results if r.command_id.endswith(":implement_amc"))
    assert "Implemented AMC geometry" in implement_result.output
