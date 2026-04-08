"""Probe CST parameter workflow support through the native Python API.

Checks:
1. Create parameters.
2. Read parameters back as string and numeric values.
3. Update parameters.
4. Create geometry using parameter expressions.
5. Rebuild after parameter change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from executor.vba_generator import VBAGenerator


def _find_parameter_index(mws, parameter_name: str) -> int:
    count = int(mws.GetNumberOfParameters())
    for index in range(count):
        if str(mws.GetParameterName(index)).strip().lower() == parameter_name.lower():
            return index
    raise ValueError(f"Parameter not found: {parameter_name}")


def run() -> int:
    result = {
        "connect": False,
        "parameter_create": False,
        "parameter_read": False,
        "parameter_update": False,
        "geometry_with_expressions": False,
        "rebuild_after_update": False,
        "macro_parameter_workflow": False,
        "depends_on_parameter": None,
        "details": {},
    }

    try:
        import cst.interface
    except Exception as exc:
        result["details"]["import_error"] = str(exc)
        print(json.dumps(result, indent=2))
        return 2

    try:
        design_env = cst.interface.DesignEnvironment.connect_to_any_or_new()
        project = design_env.new_mws()
        mws = project.model3d
        result["connect"] = True
    except Exception as exc:
        result["details"]["connect_error"] = str(exc)
        print(json.dumps(result, indent=2))
        return 3

    try:
        mws.StoreParameter("px", "37")
        mws.StoreParameter("py", "29")
        mws.StoreParameter("pz", "1.6")
        result["parameter_create"] = True
        result["details"]["parameter_names"] = [
            mws.GetParameterName(index + 1) for index in range(mws.GetNumberOfParameters())
        ]
    except Exception as exc:
        result["details"]["parameter_create_error"] = str(exc)

    try:
        px_index = _find_parameter_index(mws, "px")
        result["details"]["px_index"] = px_index
        result["details"]["px_string_before"] = mws.GetParameterSValue(px_index)
        result["details"]["px_numeric_before"] = mws.GetParameterNValue(px_index)
        result["parameter_read"] = True
    except Exception as exc:
        result["details"]["parameter_read_error"] = str(exc)

    try:
        mws.StoreDoubleParameter("px", 41.5)
        px_index = _find_parameter_index(mws, "px")
        result["details"]["px_string_after"] = mws.GetParameterSValue(px_index)
        result["details"]["px_numeric_after"] = mws.GetParameterNValue(px_index)
        result["parameter_update"] = True
    except Exception as exc:
        result["details"]["parameter_update_error"] = str(exc)

    geometry_macro = """
Component.New "antenna"
With Brick
    .Reset
    .Name "patch"
    .Component "antenna"
    .Material "PEC"
    .Xrange "-px/2", "px/2"
    .Yrange "-py/2", "py/2"
    .Zrange "0", "pz"
    .Create
End With
""".strip()

    try:
        mws.add_to_history("parametric_patch_probe", geometry_macro)
        mws.full_history_rebuild()
        result["geometry_with_expressions"] = True
    except Exception as exc:
        result["details"]["geometry_expression_error"] = str(exc)

    try:
        result["depends_on_parameter"] = bool(mws.DoesProjectDependOnParameter("px"))
    except Exception as exc:
        result["details"]["depends_on_parameter_error"] = str(exc)

    try:
        mws.StoreParameter("px", "55")
        mws.Rebuild()
        px_index = _find_parameter_index(mws, "px")
        result["details"]["px_string_final"] = mws.GetParameterSValue(px_index)
        result["details"]["px_numeric_final"] = mws.GetParameterNValue(px_index)
        result["rebuild_after_update"] = True
    except Exception as exc:
        result["details"]["rebuild_after_update_error"] = str(exc)

    try:
        generator = VBAGenerator()
        macro_sequence = [
            ("create_component", {"component": "macro_antenna"}),
            ("define_parameter", {"name": "mx", "value": 20}),
            (
                "define_brick",
                {
                    "name": "macro_patch",
                    "component": "macro_antenna",
                    "material": "PEC",
                    "xrange": ["-mx/2", "mx/2"],
                    "yrange": [-5, 5],
                    "zrange": [0, 1],
                },
            ),
            ("update_parameter", {"name": "mx", "value": 24}),
            ("rebuild_model", {}),
        ]
        for index, (command_name, params) in enumerate(macro_sequence, start=1):
            if command_name == "rebuild_model":
                mws.Rebuild()
                continue
            if command_name == "define_parameter":
                mws.StoreParameter(str(params["name"]), str(params["value"]))
                continue
            if command_name in {"update_parameter", "set_parameter"}:
                update_value = params["value"]
                if isinstance(update_value, (int, float)):
                    mws.StoreDoubleParameter(str(params["name"]), float(update_value))
                else:
                    mws.StoreParameter(str(params["name"]), str(update_value))
                continue
            mws.add_to_history(f"macro_param_probe_{index:02d}", generator.generate_macro(command_name, params))
        mws.full_history_rebuild()
        result["macro_parameter_workflow"] = True
    except Exception as exc:
        result["details"]["macro_parameter_workflow_error"] = str(exc)

    export_path = Path("artifacts") / "reports" / "cst_parameter_probe.json"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())