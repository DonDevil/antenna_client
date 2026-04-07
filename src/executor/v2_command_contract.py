"""Validate strict V2 command contracts loaded from config/schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from utils.logger import get_logger


logger = get_logger(__name__)


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

    def validate_commands(self, commands: Iterable[Any]) -> None:
        for cmd in commands:
            self.validate_command(
                command_name=str(getattr(cmd, "command", "")),
                params=getattr(cmd, "params", {}),
                seq=int(getattr(cmd, "seq", -1)),
            )

    def validate_command(self, command_name: str, params: Dict[str, Any], seq: int) -> None:
        spec = self._commands.get(command_name)
        if spec is None:
            raise ValueError(f"Command {seq}:{command_name} is not declared in strict V2 contract")

        required = self._list_of_str(spec.get("required_params"))
        missing = [key for key in required if key not in params or params.get(key) is None]
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
