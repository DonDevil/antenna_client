"""Tests for the single-source material resolver."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from utils.material_resolver import (
    MaterialChoice,
    normalize_material_name,
    resolve_materials,
    stamp_materials_on_package,
    FALLBACK_CONDUCTOR,
    FALLBACK_SUBSTRATE,
    FAMILY_DEFAULT_SUBSTRATES,
)


# ── normalize_material_name ──────────────────────────────────────────────────

def test_normalize_underscores():
    assert normalize_material_name("FR-4_(lossy)") == "FR-4 (lossy)"


def test_normalize_extra_spaces():
    assert normalize_material_name("  Rogers  RT/duroid   5880  ") == "Rogers RT/duroid 5880"


def test_normalize_empty():
    assert normalize_material_name("") == ""
    assert normalize_material_name(None) == ""


# ── resolve_materials: priority chain ────────────────────────────────────────

def test_explicit_user_choice_wins():
    """Level 1: explicit specs beat everything."""
    choice = resolve_materials(
        design_specs={
            "conductor_material": "Gold",
            "substrate_material": "Rogers RO4350B",
        },
        response_data={"conductor_material": "Copper (annealed)", "substrate_material": "FR-4 (lossy)"},
    )
    assert choice.conductor == "Gold"
    assert choice.substrate == "Rogers RO4350B"
    assert choice.conductor_source == "design_specs"
    assert choice.substrate_source == "design_specs"


def test_response_top_level_wins_when_no_specs():
    """Level 2: server optimize response top-level."""
    choice = resolve_materials(
        design_specs={},
        response_data={
            "conductor_material": "Silver",
            "substrate_material": "Rogers RO3003",
        },
    )
    assert choice.conductor == "Silver"
    assert choice.substrate == "Rogers RO3003"
    assert choice.conductor_source == "response_top_level"
    assert choice.substrate_source == "response_top_level"


def test_ann_prediction_wins_when_no_response_top_level():
    """Level 2b: ANN prediction."""
    choice = resolve_materials(
        response_data={
            "ann_prediction": {
                "conductor_material": "Gold",
                "family_parameters": {"substrate_material": "FR-4 (lossy)"},
            }
        },
    )
    assert choice.conductor == "Gold"
    assert choice.substrate == "FR-4 (lossy)"
    assert choice.conductor_source == "ann_prediction"
    assert choice.substrate_source == "ann_prediction"


def test_design_recipe_wins_when_no_response():
    """Level 3: design_recipe from command package."""
    choice = resolve_materials(
        command_package={
            "design_recipe": {
                "conductor_material": "Copper (annealed)",
                "substrate_material": "Rogers RT/duroid 5880",
            }
        },
    )
    assert choice.conductor == "Copper (annealed)"
    assert choice.substrate == "Rogers RT/duroid 5880"
    assert choice.conductor_source == "design_recipe"
    assert choice.substrate_source == "design_recipe"


def test_command_params_scan():
    """Level 4: scan individual commands."""
    choice = resolve_materials(
        command_package={
            "commands": [
                {"command": "create_substrate", "params": {"material": "Rogers RO3003"}},
                {"command": "create_patch", "params": {"material": "Silver"}},
            ]
        },
    )
    assert choice.conductor == "Silver"
    assert choice.substrate == "Rogers RO3003"
    assert choice.conductor_source == "command_params"
    assert choice.substrate_source == "command_params"


def test_family_default_substrate():
    """Level 5: family-based substrate default."""
    choice = resolve_materials(antenna_family="microstrip_patch")
    assert choice.substrate == FAMILY_DEFAULT_SUBSTRATES["microstrip_patch"]
    assert choice.conductor == FALLBACK_CONDUCTOR
    assert choice.substrate_source == "fallback"
    assert choice.conductor_source == "fallback"


def test_absolute_fallback():
    """Nothing provided → Copper + Rogers RO3003 (amc_patch default)."""
    choice = resolve_materials()
    assert choice.conductor == FALLBACK_CONDUCTOR
    assert choice.substrate == FAMILY_DEFAULT_SUBSTRATES["amc_patch"]


def test_allowed_lists_from_specs():
    """allowed_materials/allowed_substrates should pass through."""
    choice = resolve_materials(
        design_specs={
            "allowed_materials": ["Gold", "Silver"],
            "allowed_substrates": ["FR-4 (lossy)", "Rogers RO3003"],
        },
    )
    assert choice.allowed_materials == ["Gold", "Silver"]
    assert choice.allowed_substrates == ["FR-4 (lossy)", "Rogers RO3003"]
    # Conductor should be picked from the first allowed_materials entry
    assert choice.conductor == "Gold"


def test_underscore_names_normalized():
    """Names with underscores should be normalized to spaces."""
    choice = resolve_materials(
        design_specs={
            "conductor_material": "Copper_(annealed)",
            "substrate_material": "FR-4_(lossy)",
        },
    )
    assert choice.conductor == "Copper (annealed)"
    assert choice.substrate == "FR-4 (lossy)"


# ── stamp_materials_on_package ───────────────────────────────────────────────

def test_stamp_fills_missing_materials():
    """stamp_materials_on_package patches commands that lack material and prepends define_material commands."""
    package = {
        "commands": [
            {"command": "create_substrate", "params": {"name": "substrate"}},
            {"command": "create_patch", "params": {"name": "patch"}},
            {"command": "create_ground_plane", "params": {"name": "ground"}},
        ],
    }
    choice = MaterialChoice(
        conductor="Gold",
        substrate="Rogers RO4350B",
        allowed_materials=["Gold"],
        allowed_substrates=["Rogers RO4350B"],
    )
    result = stamp_materials_on_package(package, choice)

    # Now expects define_material commands prepended; find original commands by offset
    # Commands 0-1: define_material commands for Gold and Rogers RO4350B
    # Commands 2-4: original commands with material patching
    num_define_materials = sum(1 for cmd in result["commands"] if cmd.get("command") == "define_material")
    assert num_define_materials == 2  # Gold and Rogers RO4350B
    
    # Check original commands are patched correctly
    assert result["commands"][num_define_materials + 0]["params"]["material"] == "Rogers RO4350B"
    assert result["commands"][num_define_materials + 1]["params"]["material"] == "Gold"
    assert result["commands"][num_define_materials + 2]["params"]["material"] == "Gold"
    assert result["design_recipe"]["conductor_material"] == "Gold"
    assert result["design_recipe"]["substrate_material"] == "Rogers RO4350B"
    assert result["_resolved_materials"]["conductor"] == "Gold"
    assert result["_resolved_materials"]["substrate"] == "Rogers RO4350B"


def test_stamp_preserves_existing_materials():
    """stamp_materials_on_package preserves existing material assignments."""
    package = {
        "commands": [
            {"command": "create_substrate", "params": {"name": "substrate", "material": "FR-4 (lossy)"}},
            {"command": "create_patch", "params": {"name": "patch", "material": "Silver"}},
        ],
    }
    choice = MaterialChoice(
        conductor="Gold",
        substrate="Rogers RO4350B",
        allowed_materials=["Gold"],
        allowed_substrates=["Rogers RO4350B"],
    )
    result = stamp_materials_on_package(package, choice)

    # Existing materials should be preserved; check after define_material commands
    num_define_materials = sum(1 for cmd in result["commands"] if cmd.get("command") == "define_material")
    assert result["commands"][num_define_materials + 0]["params"]["material"] == "FR-4 (lossy)"
    assert result["commands"][num_define_materials + 1]["params"]["material"] == "Silver"


def test_stamp_define_brick_roles():
    """stamp_materials_on_package identifies define_brick roles by name."""
    package = {
        "commands": [
            {"command": "define_brick", "params": {"name": "substrate"}},
            {"command": "define_brick", "params": {"name": "ground"}},
            {"command": "define_brick", "params": {"name": "patch"}},
            {"command": "define_brick", "params": {"name": "feed"}},
        ],
    }
    choice = MaterialChoice(
        conductor="Copper (annealed)",
        substrate="FR-4 (lossy)",
        allowed_materials=["Copper (annealed)"],
        allowed_substrates=["FR-4 (lossy)"],
    )
    result = stamp_materials_on_package(package, choice)

    # Check after define_material commands prefixed
    num_define_materials = sum(1 for cmd in result["commands"] if cmd.get("command") == "define_material")
    assert result["commands"][num_define_materials + 0]["params"]["material"] == "FR-4 (lossy)"
    assert result["commands"][num_define_materials + 1]["params"]["material"] == "Copper (annealed)"
    assert result["commands"][num_define_materials + 2]["params"]["material"] == "Copper (annealed)"
    assert result["commands"][num_define_materials + 3]["params"]["material"] == "Copper (annealed)"


# ── integration: resolve + stamp ─────────────────────────────────────────────

def test_full_resolve_and_stamp_pipeline():
    """End-to-end: resolve from specs → stamp onto package."""
    design_specs = {
        "antenna_family": "microstrip_patch",
        "conductor_material": "Silver",
        "substrate_material": "Rogers RT/duroid 5880",
    }
    response_data = {
        "conductor_material": "Copper (annealed)",  # should be overridden by specs
        "command_package": {
            "design_recipe": {},
            "commands": [
                {"command": "create_substrate", "params": {"name": "substrate"}},
                {"command": "create_patch", "params": {"name": "patch"}},
            ],
        },
    }
    choice = resolve_materials(
        design_specs=design_specs,
        response_data=response_data,
        command_package=response_data["command_package"],
    )
    assert choice.conductor == "Silver"
    assert choice.substrate == "Rogers RT/duroid 5880"

    result = stamp_materials_on_package(response_data["command_package"], choice)
    # Account for prepended define_material commands
    num_define_materials = sum(1 for cmd in result["commands"] if cmd.get("command") == "define_material")
    assert result["commands"][num_define_materials + 0]["params"]["material"] == "Rogers RT/duroid 5880"
    assert result["commands"][num_define_materials + 1]["params"]["material"] == "Silver"
