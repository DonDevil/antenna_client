"""Interactive CST command console for validating client-to-CST communication.

Usage:
    python test_cst_command_console.py

Command input format:
    <command_name> <optional_json_params>

Examples:
    help
    create_project {"project_name": "demo_patch"}
    set_units
    set_frequency_range {"start_ghz": 1.8, "stop_ghz": 3.2}
    define_material {"name": "Copper (annealed)", "kind": "conductor", "conductivity_s_per_m": 5.8e7}
    create_substrate
    create_patch
    run_simulation
    raw {"title": "quick_note", "code": "' test line"}
    quit
"""

from __future__ import annotations

import json
import platform
import re
from pathlib import Path
from typing import Any

import cst.interface

from cst_client.cst_app import CSTApp
from executor.vba_generator import VBAGenerator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.json"


DEFAULT_PARAMS: dict[str, dict[str, Any]] = {
    "create_component": {"component": "component1"},
    "define_parameter": {"name": "px", "value": 37, "description": "Patch width"},
    "update_parameter": {"name": "px", "value": 41.5},
    "rebuild_model": {},
    "define_brick": {
        "name": "solid1",
        "component": "component1",
        "material": "PEC",
        "xrange": [-16, -4],
        "yrange": [-3, 2],
        "zrange": [-3, 0],
    },
    "set_units": {"geometry": "mm", "frequency": "ghz"},
    "set_frequency_range": {"start_ghz": 1.9, "stop_ghz": 2.9},
    "define_material": {
        "name": "Copper (annealed)",
        "kind": "conductor",
        "conductivity_s_per_m": 58000000.0,
    },
    "create_substrate": {
        "name": "substrate",
        "component": "antenna",
        "material": "FR-4 (lossy)",
        "length_mm": 56.0,
        "width_mm": 60.0,
        "height_mm": 1.6,
        "origin_mm": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "create_ground_plane": {
        "name": "ground",
        "component": "antenna",
        "material": "Copper (annealed)",
        "length_mm": 56.0,
        "width_mm": 60.0,
        "thickness_mm": 0.035,
        "z_mm": 0.0,
    },
    "create_patch": {
        "name": "patch",
        "component": "antenna",
        "material": "Copper (annealed)",
        "length_mm": 31.0,
        "width_mm": 36.0,
        "thickness_mm": 0.035,
        "center_mm": {"x": 0.0, "y": 0.0, "z": 1.6},
    },
    "create_feedline": {
        "name": "feed",
        "component": "antenna",
        "material": "Copper (annealed)",
        "length_mm": 12.5,
        "width_mm": 0.8,
        "thickness_mm": 0.035,
        "start_mm": {"x": 0.0, "y": -15.5, "z": 1.6},
        "end_mm": {"x": 0.0, "y": -28.0, "z": 1.6},
    },
    "create_port": {
        "port_id": 1,
        "port_type": "discrete",
        "impedance_ohm": 50.0,
        "p1_mm": {"x": 0.0, "y": -28.0, "z": 1.6},
        "p2_mm": {"x": 0.0, "y": -28.0, "z": 0.035},
    },
    "set_boundary": {"boundary_type": "open_add_space", "padding_mm": 15.0},
    "set_solver": {"solver_type": "time_domain", "mesh_cells_per_wavelength": 20},
    "add_farfield_monitor": {"frequency_ghz": 2.4, "name": "farfield_2p4ghz"},
    "run_simulation": {"timeout_sec": 600},
    "export_s_parameters": {"format": "json", "destination_hint": "s11"},
    "extract_summary_metrics": {
        "metrics": [
            "center_frequency_ghz",
            "bandwidth_mhz",
            "return_loss_db",
            "vswr",
            "gain_dbi",
        ]
    },
    "export_farfield": {"format": "json", "frequency_ghz": 2.4, "destination_hint": "farfield"},
    "extract_farfield_metrics": {"destination_hint": "farfield"},
}


SUPPORTED_COMMANDS = [
    "create_project",
    "create_component",
    "define_parameter",
    "update_parameter",
    "rebuild_model",
    "define_brick",
    "define_sphere",
    "define_cone",
    "define_torus",
    "define_cylinder",
    "define_ecylinder",
    "define_extrude",
    "define_rotate",
    "define_loft",
    "boolean_add",
    "boolean_intersect",
    "boolean_subtract",
    "boolean_insert",
    "pick_face",
    "pick_edge",
    "pick_endpoint",
    "calculate_port_extension_coefficient",
    "set_units",
    "set_frequency_range",
    "define_material",
    "create_substrate",
    "create_ground_plane",
    "create_patch",
    "create_feedline",
    "create_port",
    "set_boundary",
    "set_solver",
    "add_farfield_monitor",
    "run_simulation",
    "export_s_parameters",
    "extract_summary_metrics",
    "export_farfield",
    "extract_farfield_metrics",
    "raw",
    "help",
    "list",
    "quit",
    "exit",
]


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class CSTCommandConsole:
    def __init__(self) -> None:
        self.design_env = None
        self.project = None
        self.mws = None
        self.vba_generator = VBAGenerator()
        self.last_macro = ""

        self.config = load_config()
        self.cst_exe = self.config.get("cst", {}).get("executable_path", "")
        configured_project_dir = self.config.get("cst", {}).get("project_dir")
        self.project_dir = Path(configured_project_dir) if configured_project_dir else (Path.cwd() / "artifacts")
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self._history_counter = 0
        self.last_sparam_export: str | None = None
        self.last_farfield_export: str | None = None

    @staticmethod
    def _parse_frequency_ghz_from_item(item: str) -> float | None:
        match = re.search(r"(?:f\s*=\s*)?([0-9]+(?:\.[0-9]+)?)\s*(ghz|mhz|khz|hz)?", item, flags=re.IGNORECASE)
        if not match:
            return None
        value = float(match.group(1))
        unit = (match.group(2) or "ghz").lower()
        if unit == "ghz":
            return value
        if unit == "mhz":
            return value / 1_000.0
        if unit == "khz":
            return value / 1_000_000.0
        return value / 1_000_000_000.0

    def refresh_project(self) -> None:
        if self.design_env is None:
            return
        if self.design_env.has_active_project():
            self.project = self.design_env.active_project()
            self.mws = self.project.model3d

    def connect(self) -> None:
        if platform.system() != "Windows":
            raise RuntimeError("CST COM automation is only supported on Windows.")

        self.design_env = cst.interface.DesignEnvironment.connect_to_any_or_new()
        print("Connected to CST design environment.")

        self.refresh_project()
        if self.project is not None:
            print(f"Active project: {self.project.filename()}")
        else:
            self.project = None
            self.mws = None
            print("No active CST project is open. Use create_project first.")

    def create_project(self, project_name: str) -> None:
        if self.design_env is None:
            raise RuntimeError("CST not connected.")

        safe_name = "_".join(project_name.strip().split()) or "command_console_project"
        project_path = self.project_dir / f"{safe_name}.cst"

        self.project = self.design_env.new_mws()
        self.mws = self.project.model3d
        self.mws.SaveAs(str(project_path.resolve()), True)
        self.refresh_project()

        print(f"Created/activated project: {project_path.resolve()}")

    def run_vba(self, title: str, code: str) -> None:
        if self.mws is None:
            raise RuntimeError("No active CST project. Run create_project first.")

        self.last_macro = code
        self.refresh_project()
        if self.mws is None:
            raise RuntimeError("CST project handle became unavailable. Recreate or reopen the project.")
        self._history_counter += 1
        history_title = f"{title}_{self._history_counter:03d}"
        try:
            self.mws.add_to_history(history_title, code)
            self.mws.full_history_rebuild()
        except Exception as exc:
            msg = str(exc).lower()
            if title == "define_material" and "already exists" in msg:
                print("Material already exists; continuing without redefinition.")
                return
            raise
        self.refresh_project()

    def merge_params(self, command: str, user_params: dict[str, Any]) -> dict[str, Any]:
        params = dict(DEFAULT_PARAMS.get(command, {}))
        params.update(user_params)
        return params

    def execute_command(self, command: str, user_params: dict[str, Any]) -> None:
        if command == "create_project":
            name = user_params.get("project_name", "command_console_project")
            self.create_project(str(name))
            return

        if command == "raw":
            title = str(user_params.get("title", "raw_vba_test"))
            code = str(user_params.get("code", "' raw vba test"))
            self.run_vba(title, code)
            print("Raw VBA executed.")
            return

        if command == "run_simulation":
            if self.mws is None:
                raise RuntimeError("No active CST project. Run create_project first.")
            params = self.merge_params(command, user_params)
            timeout = int(params.get("timeout_sec", 600))
            self.refresh_project()
            try:
                self.mws.run_solver(timeout=timeout)
            except Exception as exc:
                raise RuntimeError(
                    "Simulation failed. Check excitation/port placement and boundary setup. "
                    f"CST error: {exc}"
                ) from exc
            self.refresh_project()
            print("Simulation completed.")
            return

        if command == "rebuild_model":
            if self.mws is None:
                raise RuntimeError("No active CST project. Run create_project first.")
            params = self.merge_params(command, user_params)
            self.refresh_project()
            if bool(params.get("full_history", False)):
                self.mws.full_history_rebuild()
            else:
                self.mws.Rebuild()
            self.refresh_project()
            print("Model rebuild completed.")
            return

        if command in {"define_parameter", "update_parameter", "set_parameter"}:
            if self.mws is None:
                raise RuntimeError("No active CST project. Run create_project first.")
            params = self.merge_params(command, user_params)
            name = str(params.get("name", "")).strip()
            if not name:
                raise RuntimeError("Parameter name is required.")
            value = params.get("value")
            if value is None:
                raise RuntimeError("Parameter value is required.")

            self.refresh_project()
            if command == "define_parameter" and params.get("description") and hasattr(self.mws, "StoreParameterWithDescription"):
                self.mws.StoreParameterWithDescription(name, str(value), str(params.get("description")))
            elif isinstance(value, (int, float)) and hasattr(self.mws, "StoreDoubleParameter"):
                self.mws.StoreDoubleParameter(name, float(value))
            else:
                self.mws.StoreParameter(name, str(value))
            self.refresh_project()
            print(f"Parameter updated via Parameter List API: {name}")
            return

        if command == "export_s_parameters":
            if self.mws is None:
                raise RuntimeError("No active CST project. Run create_project first.")
            params = self.merge_params(command, user_params)
            hint = str(params.get("destination_hint", "s11"))
            export_path = (Path("artifacts") / "exports" / f"{hint}.txt").resolve()
            export_path.parent.mkdir(parents=True, exist_ok=True)

            candidates = []
            try:
                items = list(self.mws.get_tree_items())
                exact = [item for item in items if item.startswith("1D Results\\S-Parameters\\")]
                if exact:
                    candidates.extend(exact)
                else:
                    candidates.extend([
                        r"1D Results\\S-Parameters\\S1,1",
                        r"1D Results\\S-Parameters\\S(1,1)",
                        r"1D Results\\S-Parameters\\SZmax(1),Zmax(1)",
                    ])
            except Exception:
                candidates.extend([
                    r"1D Results\\S-Parameters\\S1,1",
                    r"1D Results\\S-Parameters\\S(1,1)",
                    r"1D Results\\S-Parameters\\SZmax(1),Zmax(1)",
                ])

            exported = False
            for item in candidates:
                try:
                    self.mws.SelectTreeItem(item)
                    self.mws.StoreCurvesInASCIIFile(str(export_path))
                    if export_path.exists():
                        exported = True
                        break
                except Exception:
                    continue

            if not exported:
                raise RuntimeError(
                    "Unable to export S-parameters. "
                    f"Checked tree items: {candidates}. "
                    "Simulation may not have produced S-parameter curves."
                )

            self.last_sparam_export = str(export_path)
            print(f"Exported S-parameters: {export_path}")
            return

        if command == "extract_summary_metrics":
            params = self.merge_params(command, user_params)
            _ = params.get("metrics", [])
            if not self.last_sparam_export:
                raise RuntimeError("No exported S-parameter file found. Run export_s_parameters first.")

            path = Path(self.last_sparam_export)
            if not path.exists():
                raise RuntimeError(f"S-parameter export missing: {path}")

            freq = []
            s11_db = []
            for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith("!"):
                    continue
                parts = [p for p in line.replace(",", " ").split() if p]
                if len(parts) < 2:
                    continue
                try:
                    freq.append(float(parts[0]))
                    s11_db.append(float(parts[1]))
                except ValueError:
                    continue

            if not freq:
                raise RuntimeError("Unable to parse numeric S-parameter data from export file.")

            min_idx = min(range(len(s11_db)), key=lambda i: s11_db[i])
            center = freq[min_idx]
            threshold = -10.0
            band_idx = [i for i, v in enumerate(s11_db) if v <= threshold]
            if len(band_idx) >= 2:
                start = freq[band_idx[0]]
                stop = freq[band_idx[-1]]
                bw = max(stop - start, 0.0)
            else:
                start = stop = center
                bw = 0.0

            metrics = {
                "center_frequency": center,
                "bandwidth": bw,
                "min_s11_db": s11_db[min_idx],
                "start_freq": start,
                "stop_freq": stop,
            }
            metrics_path = (Path("artifacts") / "exports" / "summary_metrics.json").resolve()
            metrics_path.parent.mkdir(parents=True, exist_ok=True)
            metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
            print(f"Extracted metrics: {metrics}")
            print(f"Saved metrics to: {metrics_path}")
            return

        if command == "export_farfield":
            if self.mws is None:
                raise RuntimeError("No active CST project. Run create_project first.")

            params = self.merge_params(command, user_params)
            hint = str(params.get("destination_hint", "farfield"))
            frequency_ghz = float(params.get("frequency_ghz", 2.4))
            export_path = (Path("artifacts") / "exports" / f"{hint}.txt").resolve()
            summary_path = (Path("artifacts") / "exports" / f"{hint}_summary.txt").resolve()
            cut_path = (Path("artifacts") / "exports" / f"{hint}_theta_cut.txt").resolve()
            meta_path = (Path("artifacts") / "exports" / f"{hint}_meta.json").resolve()
            export_path.parent.mkdir(parents=True, exist_ok=True)

            candidates = []
            try:
                items = list(self.mws.get_tree_items())
                farfield_items = [
                    item for item in items if "farfield" in item.lower() and ("\\" in item or "/" in item)
                ]
                ranked = []
                for item in farfield_items:
                    parsed = self._parse_frequency_ghz_from_item(item)
                    score = abs(parsed - frequency_ghz) if parsed is not None else 1e9
                    ranked.append((score, item))
                ranked.sort(key=lambda x: x[0])
                candidates = [item for _, item in ranked]
            except Exception:
                candidates = []

            if not candidates:
                candidates = [
                    fr"Farfields\\farfield (f={frequency_ghz}GHz)",
                    fr"2D/3D Results\\Farfields\\farfield (f={frequency_ghz}GHz)",
                    r"Farfields\\farfield",
                ]

            exported = False
            chosen_item = None
            for item in candidates:
                try:
                    self.mws.SelectTreeItem(item)
                    farfield_plot = self.mws.FarfieldPlot
                    farfield_plot.SetFrequency(str(frequency_ghz))
                    farfield_plot.ASCIIExportSummary(str(summary_path))
                    farfield_plot.ASCIIExportAsSource(str(export_path))
                    farfield_plot.SetPlotMode("directivity")
                    farfield_plot.Vary("theta")
                    farfield_plot.Phi("0")
                    farfield_plot.Step("5")
                    farfield_plot.Plot()
                    cut_name = f"{hint}_theta_cut"
                    farfield_plot.CopyFarfieldTo1DResults(r"1D Results\Farfields", cut_name)
                    self.mws.SelectTreeItem(rf"1D Results\1D Results\Farfields\{cut_name}")
                    self.mws.StoreCurvesInASCIIFile(str(cut_path))
                    if export_path.exists() and export_path.stat().st_size > 0:
                        exported = True
                        chosen_item = item
                        break
                except Exception:
                    continue

            if not exported:
                raise RuntimeError(
                    "Unable to export far-field data. "
                    f"Checked tree items: {candidates}. "
                    "Ensure a far-field monitor exists and simulation has completed for the requested frequency."
                )

            meta_path.write_text(
                json.dumps(
                    {
                        "requested_frequency_ghz": frequency_ghz,
                        "selected_tree_item": chosen_item,
                        "export_path": str(export_path),
                        "summary_export_path": str(summary_path),
                        "theta_cut_export_path": str(cut_path),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.last_farfield_export = str(export_path)
            print(f"Exported far-field data: {export_path}")
            return

        if command == "extract_farfield_metrics":
            params = self.merge_params(command, user_params)
            hint = str(params.get("destination_hint", "farfield"))
            export_dir = (Path("artifacts") / "exports").resolve()
            summary_path = export_dir / f"{hint}_summary.txt"
            cut_path = export_dir / f"{hint}_theta_cut.txt"
            source_path = export_dir / f"{hint}.txt"
            metrics_path = export_dir / f"{hint}_metrics.json"

            metrics = CSTApp.extract_farfield_metrics_from_files(
                summary_file=str(summary_path),
                theta_cut_file=str(cut_path),
                source_file=str(source_path),
            )
            if not metrics:
                raise RuntimeError(
                    "Unable to parse far-field metrics. "
                    f"Expected files: {summary_path}, {cut_path}, {source_path}."
                )

            metrics["metrics_file"] = str(metrics_path)
            metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
            print(f"Extracted far-field metrics: {metrics}")
            print(f"Saved far-field metrics to: {metrics_path}")
            return

        params = self.merge_params(command, user_params)
        macro = self.vba_generator.generate_macro(command, params)
        self.run_vba(command, macro)
        print(f"Executed: {command}")

    @staticmethod
    def parse_line(line: str) -> tuple[str, dict[str, Any]]:
        line = line.strip()
        if not line:
            return "", {}

        parts = line.split(" ", 1)
        command = parts[0].strip().lower()
        if len(parts) == 1:
            return command, {}

        params_text = parts[1].strip()
        if not params_text:
            return command, {}

        try:
            params = json.loads(params_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON params: {e}") from e

        if not isinstance(params, dict):
            raise ValueError("JSON params must be an object.")

        return command, params

    def print_help(self) -> None:
        print("\nAvailable commands:")
        for cmd in SUPPORTED_COMMANDS:
            print(f"  - {cmd}")
        print("\nInput format:")
        print("  <command_name> <optional_json_params>")
        print("Examples:")
        print("  create_project {\"project_name\": \"demo_patch\"}")
        print("  set_units")
        print("  set_frequency_range {\"start_ghz\": 1.8, \"stop_ghz\": 3.2}")
        print("  raw {\"title\": \"quick_note\", \"code\": \"' test line\"}")
        print()

    def loop(self) -> None:
        self.print_help()

        while True:
            try:
                line = input("cst-test> ")
            except (KeyboardInterrupt, EOFError):
                print("\nExiting command console.")
                break

            try:
                command, params = self.parse_line(line)
                if not command:
                    continue

                if command in ("quit", "exit"):
                    print("Exiting command console.")
                    break

                if command in ("help", "list"):
                    self.print_help()
                    continue

                if command not in SUPPORTED_COMMANDS:
                    print(f"Unsupported command: {command}. Type 'help' to list commands.")
                    continue

                self.execute_command(command, params)

            except Exception as e:
                print(f"ERROR: {e}")


def main() -> None:
    console = CSTCommandConsole()
    console.connect()
    console.loop()


if __name__ == "__main__":
    main()
