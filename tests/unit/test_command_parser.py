"""Tests for command parser schema compatibility and validation."""

import pytest

from executor.command_parser import CommandParser


def _base_package(schema_version: str = "cst_command_package.v1") -> dict:
    return {
        "schema_version": schema_version,
        "command_catalog_version": "2026.04",
        "session_id": "sess-123",
        "trace_id": "trace-123",
        "design_id": "design-123",
        "iteration_index": 0,
        "units": {"geometry": "mm", "frequency": "ghz"},
        "predicted_dimensions": {},
        "commands": [
            {
                "seq": 1,
                "command": "set_units",
                "params": {"geometry": "mm", "frequency": "ghz"},
                "on_failure": "abort",
                "checksum_scope": "command",
            }
        ],
        "expected_exports": [],
        "safety_checks": [],
    }


def test_parser_accepts_v1_and_v2_schema_versions() -> None:
    parser = CommandParser()

    v1 = parser.parse_package(_base_package("cst_command_package.v1"))
    v2 = parser.parse_package(_base_package("cst_command_package.v2"))

    assert parser.validate_package(v1) is True
    assert parser.validate_package(v2) is True


def test_parser_rejects_unknown_schema_version() -> None:
    parser = CommandParser()
    package = parser.parse_package(_base_package("cst_command_package.v999"))

    with pytest.raises(ValueError, match="Unsupported package version"):
        parser.validate_package(package)


def test_command_alias_fields_are_normalized() -> None:
    parser = CommandParser()
    payload = _base_package("cst_command_package.v2")
    payload["commands"] = [
        {
            "seq": 1,
            "type": "define_brick",
            "parameters": {
                "name": "solid1",
                "material": "PEC",
                "xrange": [-10, 10],
                "yrange": [-5, 5],
                "zrange": [0, 1],
            },
        }
    ]

    package = parser.parse_package(payload)
    assert package.commands[0].command == "define_brick"
    assert package.commands[0].params["name"] == "solid1"
    assert package.commands[0].checksum_scope == "command"


def test_v2_validation_rejects_missing_required_command_params() -> None:
    parser = CommandParser()
    payload = _base_package("cst_command_package.v2")
    payload["commands"] = [
        {
            "seq": 1,
            "command": "define_brick",
            "params": {
                "name": "solid1",
                "xrange": [-10, 10],
                "yrange": [-5, 5],
            },
        }
    ]

    package = parser.parse_package(payload)
    with pytest.raises(ValueError, match="missing required params"):
        parser.validate_package(package)


def test_v2_validation_rejects_unknown_command() -> None:
    parser = CommandParser()
    payload = _base_package("cst_command_package.v2")
    payload["commands"] = [
        {
            "seq": 1,
            "command": "not_a_real_v2_command",
            "params": {},
        }
    ]

    package = parser.parse_package(payload)
    with pytest.raises(ValueError, match="is not declared in strict V2 contract"):
        parser.validate_package(package)
