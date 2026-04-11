"""Single authoritative material resolution for the entire client pipeline.

Every touch-point (request_builder, chat_message_handler, execution_engine)
delegates to this module instead of running its own fallback chain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


# ── family-level substrate defaults (matches server expectations) ────────────
# Note: amc_patch use Rogers RO3003 as default (user can override in UI)
FAMILY_DEFAULT_SUBSTRATES: Dict[str, str] = {
    "amc_patch": "Rogers RO3003",  # Changed: was FR-4 (lossy), now matches typical AMC substrate
    "microstrip_patch": "Rogers RT/duroid 5880",
    "wban_patch": "Rogers RO3003",
}

FALLBACK_CONDUCTOR = "Copper (annealed)"
FALLBACK_SUBSTRATE = "FR-4 (lossy)"


@dataclass
class MaterialChoice:
    """Result of a single material resolution pass."""

    conductor: str
    substrate: str
    allowed_materials: List[str] = field(default_factory=list)
    allowed_substrates: List[str] = field(default_factory=list)
    conductor_source: str = "fallback"
    substrate_source: str = "fallback"


# ── helpers ──────────────────────────────────────────────────────────────────

def _first_string(*values: Any) -> Optional[str]:
    """Return the first non-empty stripped string, or None."""
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
    return None


def _first_from_list(value: Any) -> Optional[str]:
    """Return the first non-empty string from a list, or None."""
    if isinstance(value, (list, tuple)) and value:
        return _first_string(value[0])
    return None


def _coerce_string_list(value: Any) -> List[str]:
    """Turn a scalar or list into a deduplicated list of non-empty strings."""
    if isinstance(value, (list, tuple)):
        seen: List[str] = []
        for item in value:
            text = _first_string(item)
            if text and text not in seen:
                seen.append(text)
        return seen
    text = _first_string(value)
    return [text] if text else []


def normalize_material_name(raw: Optional[str]) -> str:
    """Canonical form: spaces instead of underscores, no trailing whitespace."""
    text = str(raw or "").strip()
    text = text.replace("_", " ")
    # Collapse multiple spaces
    return " ".join(text.split())


# ── main resolver ────────────────────────────────────────────────────────────

def resolve_materials(
    *,
    design_specs: Optional[Dict[str, Any]] = None,
    response_data: Optional[Dict[str, Any]] = None,
    command_package: Optional[Dict[str, Any]] = None,
    antenna_family: Optional[str] = None,
) -> MaterialChoice:
    """Resolve conductor and substrate materials with a single priority chain.

    Priority (highest → lowest):
        1. Explicit user choice from design_specs UI fields
        2. Server optimize response (top-level + ann_prediction)
        3. Command-package design_recipe / family_parameters
        4. Command-package individual command params
        5. Family-based defaults

    Returns a MaterialChoice with the winning material names and which source
    level provided them.
    """
    specs = dict(design_specs or {})
    constraints = specs.get("constraints", {}) if isinstance(specs.get("constraints"), dict) else {}
    response = dict(response_data or {})
    package = dict(command_package or {})

    family = str(
        antenna_family
        or specs.get("antenna_family")
        or ""
    ).strip() or "amc_patch"

    # ── Conductor resolution ────────────────────────────────────────────
    conductor: Optional[str] = None
    conductor_source = "fallback"

    # Level 1: Explicit user choice from design_specs / UI
    candidate = _first_string(
        specs.get("conductor_material"),
        specs.get("conductor_name"),
        constraints.get("conductor_material"),
        constraints.get("conductor_name"),
    )
    if candidate:
        conductor, conductor_source = candidate, "design_specs"

    # Level 1b: allowed_materials list from UI
    if not conductor:
        allowed = (
            _coerce_string_list(specs.get("allowed_materials"))
            or _coerce_string_list(constraints.get("allowed_materials"))
        )
        if allowed:
            conductor, conductor_source = allowed[0], "design_specs.allowed_materials"

    # Level 2: Server optimize response top-level
    if not conductor:
        candidate = _first_string(
            response.get("conductor_material"),
            response.get("conductor_name"),
        )
        if candidate:
            conductor, conductor_source = candidate, "response_top_level"

    # Level 2b: ANN prediction
    if not conductor:
        ann = response.get("ann_prediction") if isinstance(response.get("ann_prediction"), dict) else {}
        ann_fp = ann.get("family_parameters") if isinstance(ann.get("family_parameters"), dict) else {}
        candidate = _first_string(
            ann.get("conductor_material"),
            ann_fp.get("conductor_material"),
            ann_fp.get("conductor_name"),
        )
        if candidate:
            conductor, conductor_source = candidate, "ann_prediction"

    # Level 3: Command-package design_recipe / family_parameters
    if not conductor:
        recipe = package.get("design_recipe") if isinstance(package.get("design_recipe"), dict) else {}
        fp = recipe.get("family_parameters") if isinstance(recipe.get("family_parameters"), dict) else {}
        candidate = _first_string(
            recipe.get("conductor_material"),
            recipe.get("conductor_name"),
            fp.get("conductor_material"),
            fp.get("conductor_name"),
        )
        if candidate:
            conductor, conductor_source = candidate, "design_recipe"

    # Level 4: Scan individual command params in the package
    if not conductor:
        candidate = _scan_commands_for_material(package, role="conductor")
        if candidate:
            conductor, conductor_source = candidate, "command_params"

    # Level 5: Hard fallback
    if not conductor:
        conductor = FALLBACK_CONDUCTOR

    # ── Substrate resolution ────────────────────────────────────────────
    substrate: Optional[str] = None
    substrate_source = "fallback"

    # Level 1
    candidate = _first_string(
        specs.get("substrate_material"),
        specs.get("substrate_name"),
        constraints.get("substrate_material"),
        constraints.get("substrate_name"),
    )
    if candidate:
        substrate, substrate_source = candidate, "design_specs"

    # Level 1b
    if not substrate:
        allowed = (
            _coerce_string_list(specs.get("allowed_substrates"))
            or _coerce_string_list(constraints.get("allowed_substrates"))
        )
        if allowed:
            substrate, substrate_source = allowed[0], "design_specs.allowed_substrates"

    # Level 2
    if not substrate:
        candidate = _first_string(
            response.get("substrate_material"),
            response.get("substrate_name"),
        )
        if candidate:
            substrate, substrate_source = candidate, "response_top_level"

    # Level 2b
    if not substrate:
        ann = response.get("ann_prediction") if isinstance(response.get("ann_prediction"), dict) else {}
        ann_fp = ann.get("family_parameters") if isinstance(ann.get("family_parameters"), dict) else {}
        candidate = _first_string(
            ann.get("substrate_material"),
            ann_fp.get("substrate_material"),
            ann_fp.get("substrate_name"),
        )
        if candidate:
            substrate, substrate_source = candidate, "ann_prediction"

    # Level 3
    if not substrate:
        recipe = package.get("design_recipe") if isinstance(package.get("design_recipe"), dict) else {}
        fp = recipe.get("family_parameters") if isinstance(recipe.get("family_parameters"), dict) else {}
        candidate = _first_string(
            recipe.get("substrate_material"),
            recipe.get("substrate_name"),
            fp.get("substrate_material"),
            fp.get("substrate_name"),
        )
        if candidate:
            substrate, substrate_source = candidate, "design_recipe"

    # Level 4
    if not substrate:
        candidate = _scan_commands_for_material(package, role="substrate")
        if candidate:
            substrate, substrate_source = candidate, "command_params"

    # Level 5: Family-based default
    if not substrate:
        substrate = FAMILY_DEFAULT_SUBSTRATES.get(family, FALLBACK_SUBSTRATE)

    # ── Normalize names ─────────────────────────────────────────────────
    conductor = normalize_material_name(conductor)
    substrate = normalize_material_name(substrate)

    # ── Build allowed lists ─────────────────────────────────────────────
    allowed_materials = _coerce_string_list(specs.get("allowed_materials")) or _coerce_string_list(constraints.get("allowed_materials"))
    if not allowed_materials:
        allowed_materials = [conductor]

    allowed_substrates = _coerce_string_list(specs.get("allowed_substrates")) or _coerce_string_list(constraints.get("allowed_substrates"))
    if not allowed_substrates:
        allowed_substrates = [substrate]

    choice = MaterialChoice(
        conductor=conductor,
        substrate=substrate,
        allowed_materials=allowed_materials,
        allowed_substrates=allowed_substrates,
        conductor_source=conductor_source,
        substrate_source=substrate_source,
    )
    logger.info(
        "Material resolved: conductor=%s (via %s), substrate=%s (via %s)",
        choice.conductor,
        choice.conductor_source,
        choice.substrate,
        choice.substrate_source,
    )
    return choice


def stamp_materials_on_package(
    command_package: Dict[str, Any],
    choice: MaterialChoice,
) -> Dict[str, Any]:
    """Stamp resolved materials onto the command package and its commands.

    This replaces both ``_inject_response_materials_into_command_package`` from
    chat_message_handler and the command-level patching that execution_engine
    used to do.

    Also generates define_material commands and prepends them to ensure
    materials are defined in CST before being used.
    """
    patched = dict(command_package)

    # Store in design_recipe for downstream consumers (execution_engine reads this).
    recipe = dict(patched.get("design_recipe") or {})
    recipe["substrate_material"] = choice.substrate
    recipe["conductor_material"] = choice.conductor
    patched["design_recipe"] = recipe

    # Also store at the top-level key for easy access.
    patched["_resolved_materials"] = {
        "conductor": choice.conductor,
        "substrate": choice.substrate,
        "conductor_source": choice.conductor_source,
        "substrate_source": choice.substrate_source,
    }

    # Patch individual commands that are missing materials.
    commands = list(patched.get("commands") or [])
    for cmd in commands:
        if not isinstance(cmd, dict):
            continue
        params = cmd.get("params")
        if not isinstance(params, dict):
            continue

        command_name = str(cmd.get("command", "")).strip().lower()
        solid_name = str(params.get("name", "")).strip().lower()
        existing = _first_string(params.get("material"))

        if command_name == "create_substrate" and not existing:
            params["material"] = choice.substrate
        elif command_name in {"create_ground_plane", "create_patch", "create_feedline"} and not existing:
            params["material"] = choice.conductor
        elif command_name == "define_brick":
            if solid_name == "substrate" and not existing:
                params["material"] = choice.substrate
            elif solid_name in {"ground", "patch", "feed"} and not existing:
                params["material"] = choice.conductor

    # ── Generate define_material commands for each unique material ────────────
    # Collect unique materials that will be used in the commands.
    unique_materials = set()
    for cmd in commands:
        if isinstance(cmd, dict):
            params = cmd.get("params")
            if isinstance(params, dict):
                mat = _first_string(params.get("material"))
                if mat:
                    unique_materials.add(mat)

    # Always include the resolved conductor and substrate.
    unique_materials.add(choice.conductor)
    unique_materials.add(choice.substrate)

    # Create define_material commands for each material.
    # These will be inserted at the beginning of the command list.
    material_defs = []
    material_info = {
        "copper annealed": {"kind": "conductor", "conductivity_s_per_m": 5.8e7},
        "copper": {"kind": "conductor", "conductivity_s_per_m": 5.8e7},
        "aluminum": {"kind": "conductor", "conductivity_s_per_m": 3.56e7},
        "gold": {"kind": "conductor", "conductivity_s_per_m": 4.561e7},
        "silver": {"kind": "conductor", "conductivity_s_per_m": 6.3e7},
        "fr-4 lossy": {"kind": "substrate", "epsilon_r": 4.4, "loss_tangent": 0.02},
        "fr-4": {"kind": "substrate", "epsilon_r": 4.4, "loss_tangent": 0.02},
        "rogers rt duroid 5880": {"kind": "substrate", "epsilon_r": 2.2, "loss_tangent": 0.0009},
        "rogers ro3003": {"kind": "substrate", "epsilon_r": 3.0, "loss_tangent": 0.0011},
    }

    for mat in sorted(unique_materials):
        if not mat or not isinstance(mat, str):
            continue
        # Normalize for lookup (normalize_material_name removes accents, normalizes spacing)
        mat_normalized = normalize_material_name(mat).lower()
        mat_info = material_info.get(mat_normalized, {"kind": "conductor"})

        define_cmd = {
            "seq": len(material_defs) + 1,  # Will be renumbered later if needed
            "command": "define_material",
            "params": {
                "name": mat,
                **mat_info,
            },
            "on_failure": "continue",
        }
        material_defs.append(define_cmd)

    # Prepend define_material commands to the command list.
    # Adjust sequence numbers for existing commands.
    for i, cmd in enumerate(commands):
        if isinstance(cmd, dict):
            current_seq = cmd.get("seq", i + 1)
            cmd["seq"] = current_seq + len(material_defs)

    patched["commands"] = material_defs + commands
    return patched


# ── private helpers ──────────────────────────────────────────────────────────

def _scan_commands_for_material(
    package: Dict[str, Any],
    role: str,
) -> Optional[str]:
    """Scan command list for the first material matching *role* (conductor/substrate)."""
    commands = package.get("commands")
    if not isinstance(commands, (list, tuple)):
        return None

    _SUBSTRATE_COMMANDS = {"create_substrate"}
    _CONDUCTOR_COMMANDS = {"create_ground_plane", "create_patch", "create_feedline"}
    _SUBSTRATE_BRICK_NAMES = {"substrate"}
    _CONDUCTOR_BRICK_NAMES = {"ground", "patch", "feed"}

    for cmd in commands:
        if not isinstance(cmd, dict):
            continue
        params = cmd.get("params")
        if not isinstance(params, dict):
            continue
        command_name = str(cmd.get("command", "")).strip().lower()
        solid_name = str(params.get("name", "")).strip().lower()
        material = _first_string(params.get("material"))
        if not material:
            continue

        if role == "substrate":
            if command_name in _SUBSTRATE_COMMANDS:
                return material
            if command_name == "define_brick" and solid_name in _SUBSTRATE_BRICK_NAMES:
                return material
        elif role == "conductor":
            if command_name in _CONDUCTOR_COMMANDS:
                return material
            if command_name == "define_brick" and solid_name in _CONDUCTOR_BRICK_NAMES:
                return material
    return None
