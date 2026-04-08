"""Validate strict V2 command contracts loaded from config/schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, cast

from utils.logger import get_logger


logger = get_logger(__name__)

GEOMETRY_COMMANDS_REQUIRING_COMPONENT = {
    "create_substrate",
    "create_ground_plane",
    "create_patch",
    "create_feedline",
    "define_brick",
    "define_sphere",
    "define_cone",
    "define_torus",
    "define_cylinder",
    "define_ecylinder",
    "define_extrude",
    "define_rotate",
    "define_loft",
    "brick",
    "sphere",
    "cone",
    "torus",
    "cylinder",
    "ecylinder",
    "extrude",
    "rotate",
    "loft",
}
PARAMETER_MUTATION_COMMANDS = {"define_parameter", "update_parameter", "set_parameter"}
SIMULATION_EXPORT_COMMANDS = {
    "run_simulation",
    "export_s_parameters",
    "extract_summary_metrics",
    "export_farfield",
}


class V2CommandContractValidator:
    """Command-level validator for cst_command_package.v2 payloads."""

    DEFAULT_CONTRACT_PATH = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "schema"
        / "cst_command_package.v2.command_contract.json"
    )

    def __init__(self, contract_path: Path | None = None) -> None:
        self.contract_path = contract_path or self.DEFAULT_CONTRACT_PATH
        self._commands = self._load_contract()

    def _load_contract(self) -> Dict[str, Dict[str, Any]]:
        if not self.contract_path.exists():
            raise ValueError(f"V2 command contract not found: {self.contract_path}")
        data = json.loads(self.contract_path.read_text(encoding="utf-8"))
        commands = data.get("commands")
        if not isinstance(commands, dict) or not commands:
            raise ValueError("V2 command contract must define a non-empty 'commands' map")
        logger.info("Loaded V2 command contract from %s with %d commands", self.contract_path, len(commands))
        return commands

    def validate_package(self, package: Mapping[str, Any]) -> None:
        schema_version = package.get("schema_version")
        if schema_version != "cst_command_package.v2":
            raise ValueError(
                f"Command package schema_version must be 'cst_command_package.v2', got {schema_version!r}"
            )

        commands = package.get("commands")
        if not isinstance(commands, list) or not commands:
            raise ValueError("Command package commands must be a non-empty list")

        previous_seq = 0
        last_parameter_mutation_seq: int | None = None
        rebuild_sequences: list[int] = []
        first_simulation_export_seq: int | None = None

        for index, command_raw in enumerate(commands, start=1):
            if not isinstance(command_raw, dict):
                raise ValueError(f"Command entry {index} must be an object")

            command = cast(dict[str, Any], command_raw)
            seq = command.get("seq")
            if not isinstance(seq, int):
                raise ValueError(f"Command entry {index} missing integer seq")
            if seq <= previous_seq:
                raise ValueError("Command sequence must be strictly increasing")
            previous_seq = seq

            command_name = command.get("command")
            if not isinstance(command_name, str) or not command_name.strip():
                raise ValueError(f"Command {seq} missing command name")

            params = command.get("params")
            if not isinstance(params, dict):
                raise ValueError(f"Command {seq}:{command_name} has invalid params payload")

            self.validate_command(command_name=command_name, params=params, seq=seq)

            if command_name in PARAMETER_MUTATION_COMMANDS:
                last_parameter_mutation_seq = seq
            elif command_name == "rebuild_model":
                rebuild_sequences.append(seq)
            elif command_name in SIMULATION_EXPORT_COMMANDS and first_simulation_export_seq is None:
                first_simulation_export_seq = seq

        if last_parameter_mutation_seq is not None:
            rebuild_after_mutation = [seq for seq in rebuild_sequences if seq > last_parameter_mutation_seq]
            if not rebuild_after_mutation:
                raise ValueError("Command package must include rebuild_model after parameter mutations")

            earliest_rebuild = min(rebuild_after_mutation)
            if first_simulation_export_seq is not None and earliest_rebuild > first_simulation_export_seq:
                raise ValueError(
                    "rebuild_model must appear before simulation or export commands after parameter mutations"
                )

    def validate_commands(self, commands: Iterable[Any]) -> None:
        previous_seq = 0
        for cmd in commands:
            seq = int(getattr(cmd, "seq", -1))
            if seq <= previous_seq:
                raise ValueError("Command sequence must be strictly increasing")
            previous_seq = seq
            self.validate_command(
                command_name=str(getattr(cmd, "command", "")),
                params=getattr(cmd, "params", {}),
                seq=seq,
            )

    def validate_command(self, command_name: str, params: Dict[str, Any], seq: int) -> None:
        spec = self._commands.get(command_name)
        if spec is None:
            raise ValueError(f"Command {seq}:{command_name} is not declared in strict V2 contract")

        required = self._list_of_str(spec.get("required_params"))
        missing = [key for key in required if key not in params or params.get(key) is None]

        if command_name in GEOMETRY_COMMANDS_REQUIRING_COMPONENT:
            component = params.get("component")
            if not isinstance(component, str) or not component.strip():
                if "component" not in missing:
                    missing.append("component")

        if command_name in PARAMETER_MUTATION_COMMANDS:
            name = params.get("name")
            value = params.get("value")
            if not isinstance(name, str) or not name.strip():
                if "name" not in missing:
                    missing.append("name")
            if value is None or (isinstance(value, str) and not value.strip()):
                if "value" not in missing:
                    missing.append("value")

        if missing:
            raise ValueError(
                f"Command {seq}:{command_name} missing required params: {', '.join(missing)}"
            )

        any_of_groups = spec.get("any_of", [])
        if any_of_groups:
            group_ok = False
            for group in any_of_groups:
                group_keys = self._list_of_str(group)
                if group_keys and all(key in params and params.get(key) is not None for key in group_keys):
                    group_ok = True
                    break
            if not group_ok:
                group_text = " or ".join("[" + ", ".join(self._list_of_str(g)) + "]" for g in any_of_groups)
                raise ValueError(
                    f"Command {seq}:{command_name} requires one of parameter groups: {group_text}"
                )

        non_empty_lists = self._list_of_str(spec.get("non_empty_lists"))
        for key in non_empty_lists:
            value = params.get(key)
            if not isinstance(value, list) or len(value) == 0:
                raise ValueError(f"Command {seq}:{command_name} requires non-empty list param '{key}'")

    @staticmethod
    def _list_of_str(value: Any) -> List[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Contract list field must be a list")
        return [str(item) for item in value]
