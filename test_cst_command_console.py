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
from pathlib import Path
from typing import Any

import win32com.client  # type: ignore[import-untyped]

from executor.vba_generator import VBAGenerator


CONFIG_PATH = Path(__file__).parent / "config.json"


DEFAULT_PARAMS: dict[str, dict[str, Any]] = {
    "set_units": {"geometry": "mm", "frequency": "ghz"},
    "set_frequency_range": {"start_ghz": 1.9, "stop_ghz": 2.9},
    "define_material": {
        "name": "Copper (annealed)",
        "kind": "conductor",
        "conductivity_s_per_m": 58000000.0,
    },
    "create_substrate": {
        "name": "substrate",
        "material": "FR-4 (lossy)",
        "length_mm": 56.0,
        "width_mm": 60.0,
        "height_mm": 1.6,
        "origin_mm": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "create_ground_plane": {
        "name": "ground",
        "material": "Copper (annealed)",
        "length_mm": 56.0,
        "width_mm": 60.0,
        "thickness_mm": 0.035,
        "z_mm": 0.0,
    },
    "create_patch": {
        "name": "patch",
        "material": "Copper (annealed)",
        "length_mm": 31.0,
        "width_mm": 36.0,
        "thickness_mm": 0.035,
        "center_mm": {"x": 0.0, "y": 0.0, "z": 1.6},
    },
    "create_feedline": {
        "name": "feed",
        "material": "Copper (annealed)",
        "length_mm": 14.0,
        "width_mm": 0.8,
        "thickness_mm": 0.035,
        "start_mm": {"x": 0.0, "y": -8.0, "z": 1.6},
        "end_mm": {"x": 0.0, "y": -22.0, "z": 1.6},
    },
    "create_port": {
        "port_id": 1,
        "port_type": "discrete",
        "impedance_ohm": 50.0,
        "reference_mm": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "set_boundary": {"boundary_type": "open_add_space", "padding_mm": 15.0},
    "set_solver": {"solver_type": "time_domain", "mesh_cells_per_wavelength": 20},
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
}


SUPPORTED_COMMANDS = [
    "create_project",
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
    "run_simulation",
    "export_s_parameters",
    "extract_summary_metrics",
    "export_farfield",
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
        self.app = None
        self.mws = None
        self.vba_generator = VBAGenerator()
        self.last_macro = ""

        self.config = load_config()
        self.cst_exe = self.config.get("cst", {}).get("executable_path", "")

    def connect(self) -> None:
        if platform.system() != "Windows":
            raise RuntimeError("CST COM automation is only supported on Windows.")

        try:
            self.app = win32com.client.GetObject(class_="CSTStudio.Application")
            print("Connected to existing CST instance.")
        except Exception:
            self.app = win32com.client.Dispatch("CSTStudio.Application")
            print("Started new CST instance.")

        self.mws = self._get_active_mws()
        if self.mws is None:
            print("No active CST project is open. Use create_project first.")

    def _get_active_mws(self):
        candidates = ["ActiveMWS", "active_mws", "MWS", "Active3D"]
        for attr in candidates:
            try:
                value = getattr(self.app, attr)
                if callable(value):
                    value = value()
                if value is not None:
                    return value
            except Exception:
                continue
        return None

    def create_project(self, project_name: str) -> None:
        if self.app is None:
            raise RuntimeError("CST not connected.")

        new_methods = ["NewMWS", "new_mws"]
        created = False
        for method in new_methods:
            fn = getattr(self.app, method, None)
            if fn is None:
                continue
            try:
                fn()
                created = True
                break
            except Exception:
                continue

        if not created:
            raise RuntimeError("Could not create a new CST project with available COM methods.")

        self.mws = self._get_active_mws()
        if self.mws is None:
            raise RuntimeError("Project creation succeeded but ActiveMWS is unavailable.")

        print(f"Created/activated project for command testing: {project_name}")

    def run_vba(self, title: str, code: str) -> None:
        if self.mws is None:
            raise RuntimeError("No active CST project. Run create_project first.")

        self.last_macro = code

        methods = ["AddToHistory", "add_to_history", "RunVBACode", "ExecuteVBACode"]
        for method in methods:
            fn = getattr(self.mws, method, None)
            if fn is None:
                continue
            try:
                if method.lower().endswith("history"):
                    fn(title, code)
                else:
                    fn(code)
                return
            except Exception:
                continue

        raise RuntimeError(
            "Unable to execute VBA with known COM methods. "
            "Check CST COM API for this version and update run_vba()."
        )

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
