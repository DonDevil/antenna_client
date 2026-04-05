"""Convert current server commands into CST-oriented VBA snippets."""

from __future__ import annotations

from typing import Dict, Any, List

from utils.logger import get_logger


logger = get_logger(__name__)


class VBAGenerator:
    """Generate VBA macro code from commands"""
    
    def generate_macro(self, command_type: str, parameters: Dict[str, Any]) -> str:
        """Generate VBA macro for command
        
        Args:
            command_type: Type of command
            parameters: Command parameters dict
            
        Returns:
            VBA code as string
            
        Raises:
            ValueError: If command type not supported
        """
        dispatch = {
            "create_project": self._create_project,
            "set_units": self._set_units,
            "set_frequency_range": self._set_frequency_range,
            "define_material": self._define_material,
            "create_substrate": self._create_substrate,
            "create_ground_plane": self._create_ground_plane,
            "create_patch": self._create_patch,
            "create_feedline": self._create_feedline,
            "create_port": self._create_port,
            "set_boundary": self._set_boundary,
            "set_solver": self._set_solver,
            "add_farfield_monitor": self._add_farfield_monitor,
            "run_simulation": self._run_simulation,
            "export_s_parameters": self._export_s_parameters,
            "extract_summary_metrics": self._extract_summary_metrics,
            "export_farfield": self._export_farfield,
        }
        handler = dispatch.get(command_type)
        if handler is None:
            raise ValueError(f"Unsupported command type: {command_type}")
        macro_code = handler(parameters)
        logger.debug(f"Generated macro for {command_type}")
        return macro_code

    @staticmethod
    def _brick(name: str, material: str, x_min: float, x_max: float, y_min: float, y_max: float, z_min: float, z_max: float) -> str:
        return f"""
With Brick
    .Reset
    .Name \"{name}\"
    .Component \"component1\"
    .Material \"{material}\"
    .Xrange \"{x_min}\", \"{x_max}\"
    .Yrange \"{y_min}\", \"{y_max}\"
    .Zrange \"{z_min}\", \"{z_max}\"
    .Create
End With
""".strip()

    def _create_project(self, parameters: Dict[str, Any]) -> str:
        raise ValueError("create_project must be handled by the caller, not emitted as VBA")

    def _set_units(self, parameters: Dict[str, Any]) -> str:
        return f"""
With Units
    .Geometry \"{parameters['geometry']}\"
    .Frequency \"{parameters['frequency']}\"
End With
""".strip()

    def _set_frequency_range(self, parameters: Dict[str, Any]) -> str:
        return f"Solver.FrequencyRange \"{parameters['start_ghz']}\", \"{parameters['stop_ghz']}\""

    def _define_material(self, parameters: Dict[str, Any]) -> str:
        name = parameters["name"]
        kind = parameters["kind"]
        if kind == "conductor":
            conductivity = parameters.get("conductivity_s_per_m", 5.8e7)
            return f"""
With Material
    .Reset
    .Name \"{name}\"
    .Folder \"\"
    .FrqType \"all\"
    .Type \"Lossy metal\"
    .Sigma \"{conductivity}\"
    .Create
End With
""".strip()
        epsilon_r = parameters.get("epsilon_r", 4.4)
        loss_tangent = parameters.get("loss_tangent", 0.02)
        return f"""
With Material
    .Reset
    .Name \"{name}\"
    .Folder \"\"
    .FrqType \"all\"
    .Type \"Normal\"
    .Epsilon \"{epsilon_r}\"
    .TanD \"{loss_tangent}\"
    .Create
End With
""".strip()

    def _create_substrate(self, parameters: Dict[str, Any]) -> str:
        origin = parameters["origin_mm"]
        x_min = origin["x"] - (parameters["length_mm"] / 2.0)
        x_max = origin["x"] + (parameters["length_mm"] / 2.0)
        y_min = origin["y"] - (parameters["width_mm"] / 2.0)
        y_max = origin["y"] + (parameters["width_mm"] / 2.0)
        z_min = origin["z"]
        z_max = origin["z"] + parameters["height_mm"]
        return self._brick(parameters["name"], parameters["material"], x_min, x_max, y_min, y_max, z_min, z_max)

    def _create_ground_plane(self, parameters: Dict[str, Any]) -> str:
        x_min = -(parameters["length_mm"] / 2.0)
        x_max = parameters["length_mm"] / 2.0
        y_min = -(parameters["width_mm"] / 2.0)
        y_max = parameters["width_mm"] / 2.0
        z_min = parameters["z_mm"]
        z_max = parameters["z_mm"] + parameters["thickness_mm"]
        return self._brick(parameters["name"], parameters["material"], x_min, x_max, y_min, y_max, z_min, z_max)

    def _create_patch(self, parameters: Dict[str, Any]) -> str:
        center = parameters["center_mm"]
        x_min = center["x"] - (parameters["length_mm"] / 2.0)
        x_max = center["x"] + (parameters["length_mm"] / 2.0)
        y_min = center["y"] - (parameters["width_mm"] / 2.0)
        y_max = center["y"] + (parameters["width_mm"] / 2.0)
        z_min = center["z"]
        z_max = center["z"] + parameters["thickness_mm"]
        return self._brick(parameters["name"], parameters["material"], x_min, x_max, y_min, y_max, z_min, z_max)

    def _create_feedline(self, parameters: Dict[str, Any]) -> str:
        start = parameters["start_mm"]
        end = parameters["end_mm"]
        half_width = parameters["width_mm"] / 2.0
        x_min = min(start["x"], end["x"]) - half_width
        x_max = max(start["x"], end["x"]) + half_width
        y_min = min(start["y"], end["y"]) - half_width
        y_max = max(start["y"], end["y"]) + half_width
        z_min = start["z"]
        z_max = start["z"] + parameters["thickness_mm"]
        return self._brick(parameters["name"], parameters["material"], x_min, x_max, y_min, y_max, z_min, z_max)

    def _create_port(self, parameters: Dict[str, Any]) -> str:
        p1 = parameters.get("p1_mm") or parameters.get("reference_mm")
        if p1 is None:
            raise ValueError("create_port requires p1_mm or reference_mm")
        p2 = parameters.get("p2_mm") or {"x": p1["x"], "y": p1["y"], "z": p1["z"] + 1.0}
        return f"""
With DiscretePort
    .Reset
    .PortNumber \"{parameters['port_id']}\"
    .Label \"port_{parameters['port_id']}\"
    .Type \"SParameter\"
    .Impedance \"{parameters['impedance_ohm']}\"
    .SetP1 \"False\", \"{p1['x']}\", \"{p1['y']}\", \"{p1['z']}\"
    .SetP2 \"False\", \"{p2['x']}\", \"{p2['y']}\", \"{p2['z']}\"
    .InvertDirection \"False\"
    .LocalCoordinates \"False\"
    .Monitor \"True\"
    .Create
End With
""".strip()

    def _set_boundary(self, parameters: Dict[str, Any]) -> str:
        raw_boundary = str(parameters["boundary_type"]).strip().lower()
        boundary_map = {
            "open_add_space": "expanded open",
            "open": "open",
            "expanded_open": "expanded open",
            "expanded_lf_open": "expanded lf open",
            "electric": "electric",
            "magnetic": "magnetic",
            "periodic": "periodic",
            "unit_cell": "unit cell",
            "impedance": "impedance",
            "normal": "normal",
            "tangential": "tangential",
        }
        boundary = boundary_map.get(raw_boundary)
        if boundary is None:
            raise ValueError(f"Unsupported boundary_type for CST live execution: {parameters['boundary_type']}")

        return f"""
With Boundary
    .Xmin "{boundary}"
    .Xmax "{boundary}"
    .Ymin "{boundary}"
    .Ymax "{boundary}"
    .Zmin "{boundary}"
    .Zmax "{boundary}"
End With
' padding_mm={parameters['padding_mm']}
""".strip()

    def _set_solver(self, parameters: Dict[str, Any]) -> str:
        solver_type = str(parameters["solver_type"]).lower()
        if solver_type == "time_domain":
            target = "HF Time Domain"
        elif solver_type == "frequency_domain":
            target = "HF Frequency Domain"
        else:
            raise ValueError(f"Unsupported solver_type for CST live execution: {parameters['solver_type']}")
        return f"""
ChangeSolverType \"{target}\"
' mesh_cells_per_wavelength={parameters['mesh_cells_per_wavelength']}
""".strip()

    def _run_simulation(self, parameters: Dict[str, Any]) -> str:
        return f"""
' run_simulation
' timeout_sec={parameters['timeout_sec']}
Solver.Start
""".strip()

    def _add_farfield_monitor(self, parameters: Dict[str, Any]) -> str:
        frequency_ghz = float(parameters.get("frequency_ghz", 2.4))
        name = str(parameters.get("name", f"farfield_{frequency_ghz:g}ghz"))
        return f"""
With Monitor
    .Reset
    .Name "{name}"
    .Domain "Frequency"
    .FieldType "Farfield"
    .Frequency "{frequency_ghz}"
    .Create
End With
""".strip()

    def _export_s_parameters(self, parameters: Dict[str, Any]) -> str:
        raise ValueError("export_s_parameters is not implemented for live CST execution yet")

    def _extract_summary_metrics(self, parameters: Dict[str, Any]) -> str:
        raise ValueError("extract_summary_metrics is not implemented for live CST execution yet")

    def _export_farfield(self, parameters: Dict[str, Any]) -> str:
        raise ValueError("export_farfield is not implemented for live CST execution yet")
    
    def generate_package_script(self, commands_code: List[str]) -> str:
        """Generate complete VBA script from multiple macros
        
        Args:
            commands_code: List of macro code strings
            
        Returns:
            Complete VBA script
        """
        script = "' Auto-generated VBA script for antenna design\n"
        script += "' Generated by Antenna Optimization Client\n\n"
        script += f"Option Explicit\n"
        script += f"Dim objCST\n"
        script += f"Dim objMWS\n\n"
        script += f"' Initialize CST\n"
        script += f"Set objCST = CreateObject(\"CSTStudio.Application\")\n"
        script += f"Set objMWS = objCST.ActiveMWS\n\n"
        script += f"On Error GoTo ErrorHandler\n\n"
        script += f"' Execute commands\n"
        for i, cmd in enumerate(commands_code, 1):
            script += f"' Command {i}\n"
            script += f"{cmd}\n\n"
        
        script += f"""
Exit Sub
ErrorHandler:
    MsgBox "Error " & Err.Number & ": " & Err.Description
End Sub
"""
        return script
    
    def validate_macro(self, macro_code: str) -> bool:
        """Validate VBA macro syntax (basic check)
        
        Args:
            macro_code: VBA code to validate
            
        Returns:
            True if appears valid
        """
        # Basic sanity checks
        checks = [
            "Sub" not in macro_code,  # Not a full procedure
            len(macro_code) > 0,
            "With" not in macro_code or "End With" in macro_code,  # Balanced With statements
        ]
        return all(checks)


class VBATemplateManager:
    """Manage VBA templates for custom commands"""
    
    def __init__(self, template_dir: str = "executor/templates"):
        """Initialize template manager
        
        Args:
            template_dir: Directory containing .vba template files
        """
        self.template_dir = template_dir
        self.templates = {}
        logger.info(f"VBATemplateManager initialized with dir: {template_dir}")
    
    def load_template(self, command_type: str) -> str:
        """Load VBA template for command type
        
        Args:
            command_type: Command type (e.g., 'create_patch')
            
        Returns:
            Template content as string
            
        Raises:
            FileNotFoundError: If template not found
        """
        file_path = f"{self.template_dir}/cmd_{command_type}.vba"
        try:
            with open(file_path, 'r') as f:
                template = f.read()
            self.templates[command_type] = template
            logger.debug(f"Loaded template for {command_type}")
            return template
        except FileNotFoundError:
            logger.error(f"Template not found: {file_path}")
            raise
