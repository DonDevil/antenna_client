"""Execute current server command packages in preparation or live mode."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Dict, List, Any

from cst_client.cst_app import CSTApp
from executor.command_parser import CommandPackage, Command
from executor.vba_generator import VBAGenerator
from utils.logger import get_logger
from utils.material_resolver import (
    resolve_materials,
    normalize_material_name,
    FALLBACK_CONDUCTOR,
    FALLBACK_SUBSTRATE,
)


logger = get_logger(__name__)


class ExecutionResult:
    """Result of command execution"""
    
    def __init__(self, command_id: str, success: bool, output: str = "", error: str = "", macro: str = ""):
        self.command_id = command_id
        self.success = success
        self.output = output
        self.error = error
        self.macro = macro
        self.timestamp = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "command_id": self.command_id,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "macro": self.macro,
            "timestamp": self.timestamp
        }


class ExecutionEngine:
    """Orchestrate execution of command packages"""
    
    def __init__(self):
        """Initialize execution engine"""
        self.vba_generator = VBAGenerator()
        self.current_execution = None
        self.paused = False
        self.results: List[ExecutionResult] = []
        self.cst_app = CSTApp()
        self.dry_run = True
        self.artifacts: Dict[str, Any] = {}
        self._scoped_hint_cache: Dict[str, str] = {}
        self._geometry_context: Dict[str, Dict[str, Any]] = {}
        self._parameter_context: Dict[str, Any] = {}
        self._material_context: Dict[str, Any] = {"defined": [], "by_kind": {}}
        logger.info("ExecutionEngine initialized")
    
    async def execute_command_package(self, package: CommandPackage) -> List[ExecutionResult]:
        """Execute all commands in package
        
        Args:
            package: CommandPackage to execute
            
        Returns:
            List of ExecutionResult objects
            
        Raises:
            RuntimeError: If execution fails
        """
        self.results = []
        self.artifacts = {
            "session_id": package.session_id,
            "trace_id": package.trace_id,
            "design_id": package.design_id,
            "iteration_index": int(package.iteration_index),
        }
        self._scoped_hint_cache = {}
        self._geometry_context = {}
        self._parameter_context = {}
        self._material_context = {"defined": [], "by_kind": {}}
        self.dry_run = not self.cst_app.connect()
        logger.info(f"Starting execution of package with {len(package.commands)} commands")
        
        for i, command in enumerate(package.commands):
            if self.paused:
                logger.info("Execution paused")
                # Wait until resumed
                while self.paused:
                    await asyncio.sleep(0.5)
            
            try:
                logger.info(
                    f"Executing command {i+1}/{len(package.commands)}: "
                    f"{command.seq}:{command.command}"
                )
                result = await self._execute_command(command, package)
                self.results.append(result)

                if not result.success and command.on_failure == "retry_once":
                    logger.warning(f"Retrying command {command.seq}:{command.command} once")
                    retry_result = await self._execute_command(command, package)
                    self.results.append(retry_result)
                    result = retry_result

                if not result.success and command.on_failure == "abort":
                    logger.error(f"Command {command.seq}:{command.command} failed, aborting execution")
                    break
            except Exception as e:
                logger.exception(f"Exception executing command {command.seq}:{command.command}: {e}")
                result = ExecutionResult(f"{command.seq}:{command.command}", False, error=str(e))
                self.results.append(result)
                break
        
        logger.info(f"Execution complete. {sum(1 for r in self.results if r.success)}/{len(self.results)} succeeded")
        return self.results
    
    @staticmethod
    def _sanitize_token(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return "unknown"
        return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_") or "unknown"

    def _scoped_destination_hint(self, package: CommandPackage, base_hint: str) -> str:
        base = self._sanitize_token(base_hint or "artifact")
        cached = self._scoped_hint_cache.get(base)
        if cached:
            return cached

        session_part = self._sanitize_token(package.session_id)[:16]
        design_part = self._sanitize_token(package.design_id)[:20]
        scoped = f"{session_part}_iter{int(package.iteration_index)}_{design_part}_{base}"
        self._scoped_hint_cache[base] = scoped
        return scoped

    def _record_artifact(self, key: str, path_value: Any) -> None:
        if not path_value:
            return
        try:
            self.artifacts[key] = str(Path(path_value).resolve())
        except Exception:
            self.artifacts[key] = str(path_value)

    @staticmethod
    def _as_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_number(value: Any) -> bool:
        try:
            float(value)
            return True
        except (TypeError, ValueError):
            return False

    def _get_package_extras(self, package: CommandPackage) -> Dict[str, Any]:
        extras = getattr(package, "model_extra", None)
        if isinstance(extras, dict):
            return extras
        extras = getattr(package, "__pydantic_extra__", None)
        if isinstance(extras, dict):
            return extras
        return {}

    def _extract_server_amc_family_params(self, package: CommandPackage) -> Dict[str, Any]:
        extras = self._get_package_extras(package)
        merged: Dict[str, Any] = {}
        design_recipe = extras.get("design_recipe")
        if isinstance(design_recipe, dict):
            family_params = design_recipe.get("family_parameters")
            if isinstance(family_params, dict):
                merged.update(family_params)
        package_family_params = extras.get("family_parameters")
        if isinstance(package_family_params, dict):
            merged.update(package_family_params)
        return merged

    @staticmethod
    def _first_string(*values: Any) -> str | None:
        for value in values:
            if isinstance(value, str):
                text = value.strip()
                if text:
                    return text
        return None

    @staticmethod
    def _first_from_list(value: Any) -> str | None:
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, str):
                text = first.strip()
                if text:
                    return text
        return None

    def _remember_material(self, params: Dict[str, Any]) -> None:
        name = self._first_string(params.get("name"))
        if not name:
            return
        defined = self._material_context.setdefault("defined", [])
        if isinstance(defined, list) and name not in defined:
            defined.append(name)

        kind = self._first_string(params.get("kind"), params.get("type"))
        if not kind:
            return
        kind_lower = kind.lower()
        by_kind = self._material_context.setdefault("by_kind", {})
        if not isinstance(by_kind, dict):
            return
        if kind_lower in {"conductor", "metal", "lossy metal"}:
            by_kind["conductor"] = name
        elif kind_lower in {"dielectric", "normal", "substrate"}:
            by_kind["substrate"] = name

    def _resolve_amc_materials(
        self,
        *,
        package: CommandPackage,
        command_params: Dict[str, Any],
        family_params: Dict[str, Any],
    ) -> tuple[str, str]:
        """Read materials from the pre-stamped package.

        Priority chain (first match wins):
          1. _resolved_materials (from pre-resolution by resolution engine)
          2. command_params (from implement_amc command parameters)
          3. design_recipe (from user's UI selection, stamped by stamp_materials_on_package)
          4. family_params (from server's family_parameters)
          5. FALLBACK_SUBSTRATE/FALLBACK_CONDUCTOR

        This ensures user's material selection always takes precedence over family defaults.
        """
        extras = self._get_package_extras(package)
        resolved = extras.get("_resolved_materials") if isinstance(extras.get("_resolved_materials"), dict) else {}
        recipe = extras.get("design_recipe") if isinstance(extras.get("design_recipe"), dict) else {}

        # Log what we found for debugging
        if resolved:
            logger.debug(f"Found resolved materials in extras: {resolved}")
        if recipe:
            logger.debug(f"Found design_recipe in extras with substrate={recipe.get('substrate_material')}, conductor={recipe.get('conductor_material')}")

        substrate = (
            self._first_string(
                resolved.get("substrate"),
                command_params.get("substrate_material"),
                command_params.get("substrate_name"),
                recipe.get("substrate_material"),
                recipe.get("substrate_name"),
                family_params.get("substrate_material"),
                family_params.get("substrate_name"),
            )
            or normalize_material_name(FALLBACK_SUBSTRATE)
        )
        conductor = (
            self._first_string(
                resolved.get("conductor"),
                command_params.get("conductor_material"),
                command_params.get("conductor_name"),
                recipe.get("conductor_material"),
                recipe.get("conductor_name"),
                family_params.get("conductor_material"),
                family_params.get("conductor_name"),
            )
            or normalize_material_name(FALLBACK_CONDUCTOR)
        )

        substrate = normalize_material_name(substrate)
        conductor = normalize_material_name(conductor)

        logger.info("AMC materials: substrate=%s, conductor=%s", substrate, conductor)
        self.artifacts["amc_substrate_material"] = substrate
        self.artifacts["amc_conductor_material"] = conductor
        return substrate, conductor

    def _extract_base_dims_for_amc(self, package: CommandPackage) -> Dict[str, float]:
        dims = dict(getattr(package, "predicted_dimensions", {}) or {})
        params = dict(self._parameter_context)

        px = float(params.get("px", dims.get("patch_width_mm", 37.0)))
        py = float(params.get("py", dims.get("patch_length_mm", 29.0)))
        sx = float(params.get("sx", dims.get("substrate_width_mm", 55.0)))
        sy = float(params.get("sy", dims.get("substrate_length_mm", 47.0)))
        h_sub = float(params.get("h_sub", dims.get("substrate_height_mm", 3.0)))
        t_cu = float(params.get("t_cu", dims.get("patch_height_mm", 0.035)))

        f0 = 2.45
        predicted_metrics = getattr(package, "predicted_metrics", {}) or {}
        center = predicted_metrics.get("center_frequency_ghz") if isinstance(predicted_metrics, dict) else None
        if self._is_number(center):
            f0 = float(center)

        return {
            "px": px,
            "py": py,
            "sx": sx,
            "sy": sy,
            "h_sub": h_sub,
            "t_cu": t_cu,
            "f0": max(0.1, f0),
        }

    def _build_amc_commands_heuristic(
        self,
        base_dims: Dict[str, float],
        component: str,
        substrate_material: str,
        conductor_material: str,
    ) -> List[Dict[str, Any]]:
        px = base_dims["px"]
        py = base_dims["py"]
        sx = base_dims["sx"]
        sy = base_dims["sy"]
        h_sub = base_dims["h_sub"]
        t_cu = base_dims["t_cu"]
        f0 = max(0.1, base_dims["f0"])

        wavelength_mm = 300.0 / f0
        period_min = 0.14 * wavelength_mm
        period_max = 0.24 * wavelength_mm
        period_seed = 0.65 * max(px, py)
        amc_period = max(period_min, min(period_seed, period_max))
        amc_cell = 0.90 * amc_period
        amc_gap = amc_period - amc_cell
        amc_air_gap = max(2.0, 0.02 * wavelength_mm)
        amc_sub_h = max(1.0, 0.5 * h_sub)

        nx_seed = int(round(sx / amc_period))
        ny_seed = int(round(sy / amc_period))
        amc_nx = max(5, min(11, nx_seed if nx_seed > 0 else 7))
        amc_ny = max(5, min(11, ny_seed if ny_seed > 0 else 7))
        if amc_nx % 2 == 0:
            amc_nx += 1
        if amc_ny % 2 == 0:
            amc_ny += 1

        return self._materialize_amc_brick_commands(
            component=component,
            substrate_material=substrate_material,
            conductor_material=conductor_material,
            t_cu=t_cu,
            amc_period=amc_period,
            amc_cell=amc_cell,
            amc_gap=amc_gap,
            amc_air_gap=amc_air_gap,
            amc_sub_h=amc_sub_h,
            amc_nx=amc_nx,
            amc_ny=amc_ny,
        )

    def _build_amc_commands_server(
        self,
        base_dims: Dict[str, float],
        family_params: Dict[str, Any],
        component: str,
        substrate_material: str,
        conductor_material: str,
    ) -> List[Dict[str, Any]]:
        px = base_dims["px"]
        py = base_dims["py"]
        sx = base_dims["sx"]
        sy = base_dims["sy"]
        h_sub = base_dims["h_sub"]
        t_cu = base_dims["t_cu"]
        f0 = max(0.1, base_dims["f0"])

        wavelength_mm = 300.0 / f0
        period_fallback = max(0.14 * wavelength_mm, min(0.65 * max(px, py), 0.24 * wavelength_mm))
        amc_period = float(family_params.get("amc_unit_cell_period_mm", period_fallback))
        amc_period = max(1.0, amc_period)

        amc_cell = float(family_params.get("amc_patch_size_mm", 0.90 * amc_period))
        amc_cell = max(0.1, min(amc_cell, amc_period - 0.05))

        amc_gap = float(family_params.get("amc_gap_mm", amc_period - amc_cell))
        amc_gap = max(0.05, amc_gap)

        amc_air_gap = float(family_params.get("amc_air_gap_mm", max(2.0, 0.02 * wavelength_mm)))
        amc_air_gap = max(0.0, amc_air_gap)

        amc_sub_h = float(family_params.get("amc_via_height_mm", max(1.0, 0.5 * h_sub)))
        amc_sub_h = max(0.2, amc_sub_h)

        nx_fallback = max(5, min(11, int(round(sx / amc_period)) or 7))
        ny_fallback = max(5, min(11, int(round(sy / amc_period)) or 7))
        amc_nx = int(round(float(family_params.get("amc_array_cols", nx_fallback))))
        amc_ny = int(round(float(family_params.get("amc_array_rows", ny_fallback))))

        amc_nx = max(3, min(21, amc_nx))
        amc_ny = max(3, min(21, amc_ny))
        if amc_nx % 2 == 0:
            amc_nx += 1
        if amc_ny % 2 == 0:
            amc_ny += 1

        return self._materialize_amc_brick_commands(
            component=component,
            substrate_material=substrate_material,
            conductor_material=conductor_material,
            t_cu=t_cu,
            amc_period=amc_period,
            amc_cell=amc_cell,
            amc_gap=amc_gap,
            amc_air_gap=amc_air_gap,
            amc_sub_h=amc_sub_h,
            amc_nx=amc_nx,
            amc_ny=amc_ny,
        )

    def _materialize_amc_brick_commands(
        self,
        *,
        component: str,
        substrate_material: str,
        conductor_material: str,
        t_cu: float,
        amc_period: float,
        amc_cell: float,
        amc_gap: float,
        amc_air_gap: float,
        amc_sub_h: float,
        amc_nx: int,
        amc_ny: int,
    ) -> List[Dict[str, Any]]:
        amc_size_x = amc_nx * amc_period
        amc_size_y = amc_ny * amc_period

        amc_cell_z0 = -t_cu - amc_air_gap
        amc_cell_z1 = amc_cell_z0 + t_cu
        amc_sub_z1 = amc_cell_z0
        amc_sub_z0 = amc_sub_z1 - amc_sub_h
        amc_gnd_z1 = amc_sub_z0
        amc_gnd_z0 = amc_gnd_z1 - t_cu

        commands: List[Dict[str, Any]] = [
            {
                "command": "create_component",
                "params": {"component": component},
                "on_failure": "abort",
                "checksum_scope": "geometry",
            },
            {
                "command": "define_parameter",
                "params": {"name": "amc_period", "value": amc_period},
                "on_failure": "abort",
                "checksum_scope": "geometry",
            },
            {
                "command": "define_parameter",
                "params": {"name": "amc_cell", "value": amc_cell},
                "on_failure": "abort",
                "checksum_scope": "geometry",
            },
            {
                "command": "define_parameter",
                "params": {"name": "amc_gap", "value": amc_gap},
                "on_failure": "abort",
                "checksum_scope": "geometry",
            },
            {
                "command": "define_parameter",
                "params": {"name": "amc_nx", "value": amc_nx},
                "on_failure": "abort",
                "checksum_scope": "geometry",
            },
            {
                "command": "define_parameter",
                "params": {"name": "amc_ny", "value": amc_ny},
                "on_failure": "abort",
                "checksum_scope": "geometry",
            },
            {
                "command": "define_parameter",
                "params": {"name": "amc_air_gap", "value": amc_air_gap},
                "on_failure": "abort",
                "checksum_scope": "geometry",
            },
            {
                "command": "define_parameter",
                "params": {"name": "amc_sub_h", "value": amc_sub_h},
                "on_failure": "abort",
                "checksum_scope": "geometry",
            },
            {
                "command": "define_brick",
                "params": {
                    "name": "amc_substrate",
                    "component": component,
                    "material": substrate_material,
                    "xrange": [-amc_size_x / 2.0, amc_size_x / 2.0],
                    "yrange": [-amc_size_y / 2.0, amc_size_y / 2.0],
                    "zrange": [amc_sub_z0, amc_sub_z1],
                },
                "on_failure": "abort",
                "checksum_scope": "geometry",
            },
            {
                "command": "define_brick",
                "params": {
                    "name": "amc_ground",
                    "component": component,
                    "material": conductor_material,
                    "xrange": [-amc_size_x / 2.0, amc_size_x / 2.0],
                    "yrange": [-amc_size_y / 2.0, amc_size_y / 2.0],
                    "zrange": [amc_gnd_z0, amc_gnd_z1],
                },
                "on_failure": "abort",
                "checksum_scope": "geometry",
            },
        ]

        x0 = -(amc_nx - 1) * amc_period / 2.0
        y0 = -(amc_ny - 1) * amc_period / 2.0
        for ix in range(amc_nx):
            for iy in range(amc_ny):
                cx = x0 + ix * amc_period
                cy = y0 + iy * amc_period
                commands.append(
                    {
                        "command": "define_brick",
                        "params": {
                            "name": f"amc_cell_{ix}_{iy}",
                            "component": component,
                            "material": conductor_material,
                            "xrange": [cx - (amc_cell / 2.0), cx + (amc_cell / 2.0)],
                            "yrange": [cy - (amc_cell / 2.0), cy + (amc_cell / 2.0)],
                            "zrange": [amc_cell_z0, amc_cell_z1],
                        },
                        "on_failure": "abort",
                        "checksum_scope": "geometry",
                    }
                )

        return commands

    def _build_amc_subcommands(self, command: Command, package: CommandPackage) -> List[Command]:
        strategy = str(command.params.get("strategy", "server_family_parameters")).strip().lower()
        component = str(command.params.get("component", "amc")).strip() or "amc"

        base_dims = self._extract_base_dims_for_amc(package)
        family_params = self._extract_server_amc_family_params(package)
        substrate_material, conductor_material = self._resolve_amc_materials(
            package=package,
            command_params=dict(command.params),
            family_params=family_params,
        )
        use_server = strategy in {"server", "server_family_parameters", "server_params"}
        can_use_server = use_server and self._is_number(family_params.get("amc_unit_cell_period_mm"))

        if can_use_server:
            command_dicts = self._build_amc_commands_server(
                base_dims,
                family_params,
                component,
                substrate_material,
                conductor_material,
            )
            self.artifacts["amc_impl_strategy"] = "server_family_parameters"
        else:
            command_dicts = self._build_amc_commands_heuristic(
                base_dims,
                component,
                substrate_material,
                conductor_material,
            )
            self.artifacts["amc_impl_strategy"] = "client_heuristic"

        synthetic: List[Command] = []
        seq_seed = int(command.seq) * 1000
        for idx, item in enumerate(command_dicts, start=1):
            payload = dict(item)
            payload["seq"] = seq_seed + idx
            synthetic.append(Command.model_validate(payload))
        return synthetic

    @staticmethod
    def _as_expr(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None

    @staticmethod
    def _extract_center_expr(min_expr: str, max_expr: str) -> str | None:
        # Typical CST symbolic bounds: center-(span/2), center+(span/2)
        left = re.match(r"^\s*(.+?)\s*-\s*\(.+\)\s*$", min_expr)
        right = re.match(r"^\s*(.+?)\s*\+\s*\(.+\)\s*$", max_expr)
        if left and right:
            c_left = left.group(1).strip()
            c_right = right.group(1).strip()
            if c_left == c_right:
                return c_left
        return None

    def _remember_geometry(self, command_name: str, params: Dict[str, Any]) -> None:
        if command_name == "create_substrate":
            self._geometry_context["substrate"] = dict(params)
        elif command_name == "create_ground_plane":
            self._geometry_context["ground"] = dict(params)
        elif command_name == "create_patch":
            self._geometry_context["patch"] = dict(params)
        elif command_name == "create_feedline":
            self._geometry_context["feed"] = dict(params)
        elif command_name == "define_brick":
            name = str(params.get("name", "")).strip().lower()
            component = str(params.get("component", "")).strip().lower()
            if "substrate" in name:
                # Keep antenna substrate as primary context for feed/port derivation.
                if component == "antenna" or "substrate" not in self._geometry_context:
                    self._geometry_context["substrate"] = dict(params)
            elif "ground" in name:
                # Do not let AMC reflector ground overwrite patch-ground reference.
                if component == "antenna" or "ground" not in self._geometry_context:
                    self._geometry_context["ground"] = dict(params)
            elif "patch" in name:
                self._geometry_context["patch"] = dict(params)
            elif "feed" in name:
                self._geometry_context["feed"] = dict(params)

    def _get_y_bounds(self, geom: Dict[str, Any] | None) -> tuple[float, float] | None:
        if not geom:
            return None
        yrange = geom.get("yrange")
        if isinstance(yrange, (list, tuple)) and len(yrange) >= 2:
            y0 = self._as_float(yrange[0])
            y1 = self._as_float(yrange[1])
            if y0 is not None and y1 is not None:
                return (min(y0, y1), max(y0, y1))

        start = geom.get("start_mm") or {}
        end = geom.get("end_mm") or {}
        y0 = self._as_float(start.get("y"))
        y1 = self._as_float(end.get("y"))
        if y0 is not None and y1 is not None:
            return (min(y0, y1), max(y0, y1))
        if y0 is not None:
            return (y0, y0)
        if y1 is not None:
            return (y1, y1)

        center = geom.get("center_mm") or geom.get("origin_mm") or {}
        center_y = self._as_float(center.get("y"))
        length = self._as_float(geom.get("length_mm"))
        if center_y is not None and length is not None:
            half = length / 2.0
            return (center_y - half, center_y + half)
        return None

    def _get_y_bounds_expr(self, geom: Dict[str, Any] | None) -> tuple[str, str] | None:
        if not geom:
            return None
        yrange = geom.get("yrange")
        if isinstance(yrange, (list, tuple)) and len(yrange) >= 2:
            y0 = self._as_expr(yrange[0])
            y1 = self._as_expr(yrange[1])
            if y0 is not None and y1 is not None:
                return (y0, y1)

        start = geom.get("start_mm") or {}
        end = geom.get("end_mm") or {}
        y0 = self._as_expr(start.get("y"))
        y1 = self._as_expr(end.get("y"))
        if y0 is not None and y1 is not None:
            return (y0, y1)
        if y0 is not None:
            return (y0, y0)
        if y1 is not None:
            return (y1, y1)
        return None

    def _get_x_center(self, geom: Dict[str, Any] | None) -> float | None:
        if not geom:
            return None
        xrange = geom.get("xrange")
        if isinstance(xrange, (list, tuple)) and len(xrange) >= 2:
            x0 = self._as_float(xrange[0])
            x1 = self._as_float(xrange[1])
            if x0 is not None and x1 is not None:
                return (x0 + x1) / 2.0

        start = geom.get("start_mm") or {}
        end = geom.get("end_mm") or {}
        x0 = self._as_float(start.get("x"))
        x1 = self._as_float(end.get("x"))
        if x0 is not None and x1 is not None:
            return (x0 + x1) / 2.0
        if x0 is not None:
            return x0
        if x1 is not None:
            return x1

        center = geom.get("center_mm") or geom.get("origin_mm") or {}
        return self._as_float(center.get("x"))

    def _get_x_center_expr(self, geom: Dict[str, Any] | None) -> str | None:
        if not geom:
            return None
        xrange = geom.get("xrange")
        if isinstance(xrange, (list, tuple)) and len(xrange) >= 2:
            x0n = self._as_float(xrange[0])
            x1n = self._as_float(xrange[1])
            if x0n is not None and x1n is not None:
                return str((x0n + x1n) / 2.0)
            x0 = self._as_expr(xrange[0])
            x1 = self._as_expr(xrange[1])
            if x0 and x1:
                center_expr = self._extract_center_expr(x0, x1)
                if center_expr:
                    return center_expr

        start = geom.get("start_mm") or {}
        end = geom.get("end_mm") or {}
        x0 = self._as_expr(start.get("x"))
        x1 = self._as_expr(end.get("x"))
        if x0 and x1:
            if x0 == x1:
                return x0
            x0n = self._as_float(x0)
            x1n = self._as_float(x1)
            if x0n is not None and x1n is not None:
                return str((x0n + x1n) / 2.0)
        if x0:
            return x0
        if x1:
            return x1

        center = geom.get("center_mm") or geom.get("origin_mm") or {}
        return self._as_expr(center.get("x"))

    def _get_z_min(self, geom: Dict[str, Any] | None) -> float | None:
        if not geom:
            return None
        zrange = geom.get("zrange")
        if isinstance(zrange, (list, tuple)) and len(zrange) >= 2:
            z0 = self._as_float(zrange[0])
            z1 = self._as_float(zrange[1])
            if z0 is not None and z1 is not None:
                return min(z0, z1)

        start = geom.get("start_mm") or {}
        end = geom.get("end_mm") or {}
        z0 = self._as_float(start.get("z"))
        z1 = self._as_float(end.get("z"))
        if z0 is not None and z1 is not None:
            return min(z0, z1)
        if z0 is not None:
            return z0
        if z1 is not None:
            return z1

        center = geom.get("center_mm") or geom.get("origin_mm") or {}
        return self._as_float(center.get("z"))

    def _get_ground_top_z(self, geom: Dict[str, Any] | None) -> float | None:
        if not geom:
            return None
        zrange = geom.get("zrange")
        if isinstance(zrange, (list, tuple)) and len(zrange) >= 2:
            z0 = self._as_float(zrange[0])
            z1 = self._as_float(zrange[1])
            if z0 is not None and z1 is not None:
                return max(z0, z1)

        z_base = self._as_float(geom.get("z_mm"))
        thickness = self._as_float(geom.get("thickness_mm"))
        if z_base is not None and thickness is not None:
            return z_base + thickness
        return None

    def _get_z_min_expr(self, geom: Dict[str, Any] | None) -> str | None:
        if not geom:
            return None
        zrange = geom.get("zrange")
        if isinstance(zrange, (list, tuple)) and len(zrange) >= 2:
            z0 = self._as_expr(zrange[0])
            z1 = self._as_expr(zrange[1])
            if z0 and z1:
                z0n = self._as_float(z0)
                z1n = self._as_float(z1)
                if z0n is not None and z1n is not None:
                    return str(min(z0n, z1n))
                return z0

        start = geom.get("start_mm") or {}
        end = geom.get("end_mm") or {}
        z0 = self._as_expr(start.get("z"))
        z1 = self._as_expr(end.get("z"))
        if z0 and z1:
            if z0 == z1:
                return z0
            z0n = self._as_float(z0)
            z1n = self._as_float(z1)
            if z0n is not None and z1n is not None:
                return str(min(z0n, z1n))
            return z0
        if z0:
            return z0
        if z1:
            return z1
        return None

    def _get_ground_top_z_expr(self, geom: Dict[str, Any] | None) -> str | None:
        if not geom:
            return None
        zrange = geom.get("zrange")
        if isinstance(zrange, (list, tuple)) and len(zrange) >= 2:
            z0 = self._as_expr(zrange[0])
            z1 = self._as_expr(zrange[1])
            if z0 and z1:
                z0n = self._as_float(z0)
                z1n = self._as_float(z1)
                if z0n is not None and z1n is not None:
                    return str(max(z0n, z1n))
                return z1

        z_base = self._as_float(geom.get("z_mm"))
        thickness = self._as_float(geom.get("thickness_mm"))
        if z_base is not None and thickness is not None:
            return str(z_base + thickness)
        return None

    def _derive_feed_brick_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        derived = dict(params)
        patch_bounds = self._get_y_bounds(self._geometry_context.get("patch"))
        substrate_bounds = self._get_y_bounds(self._geometry_context.get("substrate"))
        yrange = derived.get("yrange")
        if not isinstance(yrange, (list, tuple)) or len(yrange) < 2:
            return derived

        if patch_bounds and substrate_bounds:
            patch_y_min = patch_bounds[0]
            substrate_y_min = substrate_bounds[0]
            if substrate_y_min < patch_y_min:
                derived["yrange"] = [substrate_y_min, patch_y_min]
                return derived

        patch_expr = self._get_y_bounds_expr(self._geometry_context.get("patch"))
        substrate_expr = self._get_y_bounds_expr(self._geometry_context.get("substrate"))
        if patch_expr and substrate_expr:
            derived["yrange"] = [substrate_expr[0], patch_expr[0]]
            return derived

        return derived

    def _derive_feedline_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        derived = dict(params)
        patch = self._geometry_context.get("patch")
        substrate = self._geometry_context.get("substrate")
        if not patch or not substrate:
            return derived

        patch_center = patch.get("center_mm") or {}
        substrate_origin = substrate.get("origin_mm") or {}
        patch_center_y = self._as_float(patch_center.get("y"))
        patch_center_z = self._as_float(patch_center.get("z"))
        substrate_center_y = self._as_float(substrate_origin.get("y"))
        patch_length = self._as_float(patch.get("length_mm"))
        substrate_length = self._as_float(substrate.get("length_mm"))
        if None in {patch_center_y, patch_center_z, substrate_center_y, patch_length, substrate_length}:
            return derived

        start = params.get("start_mm") or {}
        end = params.get("end_mm") or {}
        feed_x = self._as_float(start.get("x"))
        if feed_x is None:
            feed_x = self._as_float(end.get("x"))
        if feed_x is None:
            feed_x = 0.0

        feed_z = self._as_float(start.get("z"))
        if feed_z is None:
            feed_z = self._as_float(end.get("z"))
        if feed_z is None:
            feed_z = patch_center_z
        if feed_z is None:
            return derived

        y_start = patch_center_y - (patch_length / 2.0)
        y_end = substrate_center_y - (substrate_length / 2.0)
        derived["start_mm"] = {"x": feed_x, "y": y_start, "z": feed_z}
        derived["end_mm"] = {"x": feed_x, "y": y_end, "z": feed_z}
        derived["length_mm"] = abs(y_end - y_start)
        return derived

    def _derive_port_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        derived = dict(params)
        if derived.get("p1_mm") and derived.get("p2_mm"):
            derived.setdefault("calculate_port_extension", False)
            return derived

        feed = self._geometry_context.get("feed")
        ground = self._geometry_context.get("ground")
        if not feed or not ground:
            return derived

        feed_bounds = self._get_y_bounds(feed)
        x_val = self._get_x_center(feed)
        feed_z = self._get_z_min(feed)
        ground_top_z = self._get_ground_top_z(ground)

        if feed_bounds and None not in {x_val, feed_z, ground_top_z}:
            port_y = feed_bounds[0]
            derived["p1_mm"] = {"x": x_val, "y": port_y, "z": feed_z}
            derived["p2_mm"] = {"x": x_val, "y": port_y, "z": ground_top_z}
            derived.setdefault("calculate_port_extension", False)
            return derived

        feed_bounds_expr = self._get_y_bounds_expr(feed)
        x_expr = self._get_x_center_expr(feed)
        feed_z_expr = self._get_z_min_expr(feed)
        ground_top_expr = self._get_ground_top_z_expr(ground)
        if feed_bounds_expr and x_expr and feed_z_expr and ground_top_expr:
            port_y = feed_bounds_expr[0]
            derived["p1_mm"] = {"x": x_expr, "y": port_y, "z": feed_z_expr}
            derived["p2_mm"] = {"x": x_expr, "y": port_y, "z": ground_top_expr}
            derived.setdefault("calculate_port_extension", False)
        return derived

    def _build_history_title(self, command: Command, macro_params: Dict[str, Any]) -> str:
        command_name = str(command.command or "command").strip().lower()
        detail = ""

        if command_name in {"define_parameter", "update_parameter", "set_parameter"}:
            pname = str(macro_params.get("name", "")).strip()
            if pname:
                detail = pname
        elif command_name in {"define_brick", "brick", "create_patch", "create_substrate", "create_ground_plane", "create_feedline"}:
            component = str(macro_params.get("component", "")).strip()
            name = str(macro_params.get("name", "")).strip()
            if component and name:
                detail = f"{component}.{name}"
            elif name:
                detail = name
            elif component:
                detail = component
        elif command_name in {"create_component", "new_component"}:
            detail = str(macro_params.get("component") or macro_params.get("name") or "").strip()
        elif command_name == "define_material":
            detail = str(macro_params.get("name") or "").strip()
        elif command_name == "create_port":
            port_id = macro_params.get("port_id")
            if port_id is not None:
                detail = f"port_{port_id}"

        base = command_name if not detail else f"{command_name} {detail}"
        return base[:80]

    async def _execute_command(self, command: Command, package: CommandPackage) -> ExecutionResult:
        """Execute single command
        
        Args:
            command: Command to execute
            
        Returns:
            ExecutionResult
        """
        try:
            if command.command == "create_project":
                project_name = str(command.params.get("project_name", "server_generated_project"))
                project_path = self.cst_app.create_project(project_name) if not self.dry_run else None
                if not self.dry_run and not project_path:
                    return ExecutionResult(
                        f"{command.seq}:{command.command}",
                        success=False,
                        error=f"Failed to create CST project: {project_name}",
                    )
                mode = "prepared" if self.dry_run else "executed"
                return ExecutionResult(
                    f"{command.seq}:{command.command}",
                    success=True,
                    output=f"{mode.capitalize()} create_project successfully",
                    macro="",
                )

            if command.command == "run_simulation":
                timeout_sec = int(command.params.get("timeout_sec", 600))
                if not self.dry_run and not self.cst_app.run_simulation(timeout_sec=timeout_sec):
                    return ExecutionResult(
                        f"{command.seq}:{command.command}",
                        success=False,
                        error=f"Failed to run simulation with timeout_sec={timeout_sec}",
                    )
                mode = "prepared" if self.dry_run else "executed"
                return ExecutionResult(
                    f"{command.seq}:{command.command}",
                    success=True,
                    output=f"{mode.capitalize()} run_simulation successfully",
                    macro="",
                )

            if command.command == "rebuild_model":
                full_history = bool(command.params.get("full_history", False))
                vba_code = self.vba_generator.generate_macro(command.command, command.params)
                artifacts_dir = Path("artifacts") / "vba"
                artifacts_dir.mkdir(parents=True, exist_ok=True)
                macro_path = artifacts_dir / f"{command.seq:02d}_{command.command}.bas"
                macro_path.write_text(vba_code, encoding="utf-8")
                if not self.dry_run and not self.cst_app.rebuild_model(full_history=full_history):
                    return ExecutionResult(
                        f"{command.seq}:{command.command}",
                        success=False,
                        error=f"Failed to rebuild CST model (full_history={full_history})",
                        macro=vba_code,
                    )
                mode = "prepared" if self.dry_run else "executed"
                return ExecutionResult(
                    f"{command.seq}:{command.command}",
                    success=True,
                    output=f"{mode.capitalize()} rebuild_model successfully",
                    macro=vba_code,
                )

            if command.command in {"define_parameter", "update_parameter", "set_parameter"}:
                name = str(command.params.get("name", "")).strip()
                value = command.params.get("value")
                description = command.params.get("description")
                create_only = command.command == "define_parameter"
                vba_code = self.vba_generator.generate_macro(command.command, command.params)
                artifacts_dir = Path("artifacts") / "vba"
                artifacts_dir.mkdir(parents=True, exist_ok=True)
                macro_path = artifacts_dir / f"{command.seq:02d}_{command.command}.bas"
                macro_path.write_text(vba_code, encoding="utf-8")
                if not self.dry_run and not self.cst_app.set_parameter(
                    name=name,
                    value=value,
                    description=description,
                    create_only=create_only,
                ):
                    return ExecutionResult(
                        f"{command.seq}:{command.command}",
                        success=False,
                        error=f"Failed to set CST parameter '{name}'",
                        macro=vba_code,
                    )
                mode = "prepared" if self.dry_run else "executed"
                action = "define_parameter" if create_only else "update_parameter"
                if name:
                    self._parameter_context[name] = value
                return ExecutionResult(
                    f"{command.seq}:{command.command}",
                    success=True,
                    output=f"{mode.capitalize()} {action} via Parameter List API",
                    macro=vba_code,
                )

            if command.command == "define_material":
                self._remember_material(dict(command.params))

            if command.command == "implement_amc":
                subcommands = self._build_amc_subcommands(command, package)
                for subcommand in subcommands:
                    sub_result = await self._execute_command(subcommand, package)
                    if not sub_result.success:
                        return ExecutionResult(
                            f"{command.seq}:{command.command}",
                            success=False,
                            error=(
                                "Failed while expanding implement_amc via "
                                f"{subcommand.command}: {sub_result.error}"
                            ),
                        )
                self.artifacts["amc_implemented"] = True
                self.artifacts["amc_component"] = str(command.params.get("component", "amc"))
                return ExecutionResult(
                    f"{command.seq}:{command.command}",
                    success=True,
                    output=(
                        "Implemented AMC geometry via "
                        f"{self.artifacts.get('amc_impl_strategy', 'client_heuristic')} "
                        f"with {len(subcommands)} generated commands"
                    ),
                    macro="",
                )

            if command.command == "export_s_parameters":
                base_hint = str(command.params.get("destination_hint", "s11"))
                destination_hint = self._scoped_destination_hint(package, base_hint)
                if not self.dry_run:
                    exported_path = self.cst_app.export_s_parameters(destination_hint=destination_hint)
                    if not exported_path:
                        return ExecutionResult(
                            f"{command.seq}:{command.command}",
                            success=False,
                            error="Failed to export S-parameters from CST",
                        )
                    self._record_artifact("s11_trace_path", exported_path)
                    self.artifacts["s11_destination_hint"] = destination_hint
                    output = f"Exported S-parameters to {exported_path}"
                else:
                    output = "Prepared export_s_parameters in dry-run mode"
                return ExecutionResult(
                    f"{command.seq}:{command.command}",
                    success=True,
                    output=output,
                    macro="",
                )

            if command.command == "extract_summary_metrics":
                if not self.dry_run:
                    base_hint = str(command.params.get("destination_hint", "s11"))
                    destination_hint = self._scoped_destination_hint(package, base_hint)
                    sparam_path = self.cst_app.export_s_parameters(destination_hint=destination_hint)
                    if not sparam_path:
                        return ExecutionResult(
                            f"{command.seq}:{command.command}",
                            success=False,
                            error="Failed to export S-parameters before metric extraction",
                        )
                    metrics = self.cst_app.extract_summary_metrics(sparam_path)
                    if not metrics:
                        return ExecutionResult(
                            f"{command.seq}:{command.command}",
                            success=False,
                            error="Failed to parse summary metrics from S-parameter export",
                        )
                    summary_metrics_path = (Path("artifacts") / "exports" / f"{destination_hint}_summary_metrics.json").resolve()
                    summary_payload = {
                        "s11_metrics": metrics,
                        "farfield_metrics": None,
                        "session_id": package.session_id,
                        "trace_id": package.trace_id,
                        "design_id": package.design_id,
                        "iteration_index": int(package.iteration_index),
                        "destination_hint": destination_hint,
                    }
                    summary_metrics_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
                    self._record_artifact("s11_trace_path", sparam_path)
                    self._record_artifact("summary_metrics_path", summary_metrics_path)
                    self.artifacts["s11_destination_hint"] = destination_hint
                    output = f"Extracted metrics: {json.dumps(metrics)}"
                else:
                    output = "Prepared extract_summary_metrics in dry-run mode"
                return ExecutionResult(
                    f"{command.seq}:{command.command}",
                    success=True,
                    output=output,
                    macro="",
                )

            if command.command == "export_farfield":
                base_hint = str(command.params.get("destination_hint", "farfield"))
                destination_hint = self._scoped_destination_hint(package, base_hint)
                frequency_ghz = float(command.params.get("frequency_ghz", 2.4))
                if not self.dry_run:
                    exported_path = self.cst_app.export_farfield(
                        frequency_ghz=frequency_ghz,
                        destination_hint=destination_hint,
                    )
                    if not exported_path:
                        return ExecutionResult(
                            f"{command.seq}:{command.command}",
                            success=False,
                            error="Failed to export far-field data from CST",
                        )
                    farfield_metrics_path = (Path("artifacts") / "exports" / f"{destination_hint}_metrics.json").resolve()
                    farfield_summary_path = (Path("artifacts") / "exports" / f"{destination_hint}_summary.txt").resolve()
                    farfield_theta_cut_path = (Path("artifacts") / "exports" / f"{destination_hint}_theta_cut.txt").resolve()
                    farfield_metadata_path = (Path("artifacts") / "exports" / f"{destination_hint}_meta.json").resolve()
                    metrics = self.cst_app.extract_farfield_metrics(destination_hint=destination_hint)
                    self._record_artifact("farfield_source_path", exported_path)
                    self._record_artifact("farfield_metrics_path", farfield_metrics_path)
                    self._record_artifact("farfield_summary_path", farfield_summary_path)
                    self._record_artifact("farfield_theta_cut_path", farfield_theta_cut_path)
                    self._record_artifact("farfield_metadata_path", farfield_metadata_path)
                    self.artifacts["farfield_destination_hint"] = destination_hint
                    if metrics:
                        output = (
                            f"Exported far-field data to {exported_path}; "
                            f"main_lobe={metrics.get('main_lobe_direction_deg')} deg, "
                            f"beamwidth_3db={metrics.get('beamwidth_3db_deg')} deg, "
                            f"max_realized_gain={metrics.get('max_realized_gain_dbi')} dBi"
                        )
                    else:
                        output = f"Exported far-field data to {exported_path}"
                else:
                    output = "Prepared export_farfield in dry-run mode"
                return ExecutionResult(
                    f"{command.seq}:{command.command}",
                    success=True,
                    output=output,
                    macro="",
                )

            if command.command == "extract_farfield_metrics":
                base_hint = str(command.params.get("destination_hint", "farfield"))
                destination_hint = self._scoped_destination_hint(package, base_hint)
                if not self.dry_run:
                    metrics = self.cst_app.extract_farfield_metrics(destination_hint=destination_hint)
                    if not metrics:
                        return ExecutionResult(
                            f"{command.seq}:{command.command}",
                            success=False,
                            error=(
                                "Failed to extract far-field metrics. "
                                "Run export_farfield first for the same destination_hint."
                            ),
                        )
                    self._record_artifact("farfield_metrics_path", Path("artifacts") / "exports" / f"{destination_hint}_metrics.json")
                    self.artifacts["farfield_destination_hint"] = destination_hint
                    output = f"Extracted far-field metrics: {json.dumps(metrics)}"
                else:
                    output = "Prepared extract_farfield_metrics in dry-run mode"
                return ExecutionResult(
                    f"{command.seq}:{command.command}",
                    success=True,
                    output=output,
                    macro="",
                )

            # Generate VBA for command, applying client-side geometry fixes for legacy convenience commands.
            macro_params = dict(command.params)
            if command.command == "create_feedline":
                macro_params = self._derive_feedline_params(macro_params)
            elif command.command == "define_brick":
                name = str(macro_params.get("name", "")).strip().lower()
                if "feed" in name:
                    macro_params = self._derive_feed_brick_params(macro_params)
            elif command.command == "create_port":
                macro_params = self._derive_port_params(macro_params)

            vba_code = self.vba_generator.generate_macro(command.command, macro_params)

            artifacts_dir = Path("artifacts") / "vba"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            macro_path = artifacts_dir / f"{command.seq:02d}_{command.command}.bas"
            macro_path.write_text(vba_code, encoding="utf-8")

            # Execute live against CST; command failures are surfaced to on_failure policy.
            if not self.dry_run:
                history_title = self._build_history_title(command, macro_params)
                try:
                    executed = self.cst_app.execute_macro(vba_code, title=history_title)
                except TypeError:
                    # Backward compatibility for older CSTApp mocks/stubs without title kwarg.
                    executed = self.cst_app.execute_macro(vba_code)
                if not executed:
                    return ExecutionResult(
                        f"{command.seq}:{command.command}",
                        success=False,
                        error=(
                            "Failed to execute macro in CST for "
                            f"{command.seq}:{command.command}"
                        ),
                        macro=vba_code,
                    )

            await asyncio.sleep(0.1)
            mode = "prepared" if self.dry_run else "executed"
            result = ExecutionResult(
                f"{command.seq}:{command.command}",
                success=True,
                output=f"{mode.capitalize()} {command.command} successfully",
                macro=vba_code,
            )
            self._remember_geometry(command.command, macro_params)
            logger.debug(f"Command {command.seq}:{command.command} execution successful")
            return result
        except Exception as e:
            logger.error(f"Command {command.seq}:{command.command} execution failed: {e}")
            return ExecutionResult(
                f"{command.seq}:{command.command}",
                success=False,
                error=str(e),
                macro=vba_code if 'vba_code' in locals() else "",
            )
    
    def pause_execution(self) -> None:
        """Pause execution"""
        self.paused = True
        logger.info("Execution paused")
    
    def resume_execution(self) -> None:
        """Resume execution"""
        self.paused = False
        logger.info("Execution resumed")
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current execution progress
        
        Returns:
            Dictionary with progress info
        """
        total = len(self.results)
        completed = sum(1 for r in self.results if r.success)
        
        return {
            "total": total,
            "completed": completed,
            "failed": sum(1 for r in self.results if not r.success),
            "in_progress": False,
            "paused": self.paused,
            "dry_run": self.dry_run,
        }
    
    def get_results(self) -> List[Dict[str, Any]]:
        """Get all execution results
        
        Returns:
            List of result dictionaries
        """
        return [r.to_dict() for r in self.results]

    def get_artifacts(self) -> Dict[str, Any]:
        """Get exact artifact paths produced for the current package execution."""
        return dict(self.artifacts)
