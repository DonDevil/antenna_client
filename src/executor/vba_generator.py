"""Convert current server commands into CST-oriented VBA snippets."""

from __future__ import annotations

import re
from typing import Dict, Any, List

from utils.logger import get_logger


logger = get_logger(__name__)


class VBAGenerator:
    """Generate VBA macro code from commands"""

    DEFAULT_COMPONENT = "component1"

    @staticmethod
    def _sanitize_cst_name(value: Any) -> str:
        """Normalize names for CST object/material identifiers.

        CST rejects names containing characters such as `/`, `\\`, `:` and others.
        """
        raw = str(value).strip()
        if not raw:
            return "unnamed"
        sanitized = re.sub(r'[~\[\]:,|*/\\$"^<>?]+', "_", raw)
        sanitized = re.sub(r"\s+", "_", sanitized)
        sanitized = re.sub(r"_+", "_", sanitized).strip("_")
        return sanitized or "unnamed"

    @staticmethod
    def _to_bool_string(value: Any) -> str:
        if isinstance(value, bool):
            return "True" if value else "False"
        normalized = str(value).strip().lower()
        return "True" if normalized in {"1", "true", "yes", "on"} else "False"

    @staticmethod
    def _component_object_name(component: Any, solid: Any) -> str:
        return f"{VBAGenerator._sanitize_cst_name(component)}:{VBAGenerator._sanitize_cst_name(solid)}"

    @staticmethod
    def _is_numeric_value(value: Any) -> bool:
        if isinstance(value, (int, float)):
            return True
        if not isinstance(value, str):
            return False
        try:
            float(value.strip())
            return True
        except ValueError:
            return False

    @classmethod
    def _format_cst_value(cls, value: Any) -> str:
        if cls._is_numeric_value(value):
            return str(float(value))
        return str(value).strip()

    @classmethod
    def _expr_binary(cls, left: Any, operator: str, right: Any) -> Any:
        if cls._is_numeric_value(left) and cls._is_numeric_value(right):
            left_value = float(left)
            right_value = float(right)
            if operator == "+":
                return left_value + right_value
            if operator == "-":
                return left_value - right_value
            if operator == "/":
                return left_value / right_value
        return f"({cls._format_cst_value(left)}){operator}({cls._format_cst_value(right)})"

    @classmethod
    def _centered_bounds(cls, center: Any, span: Any) -> tuple[Any, Any]:
        half_span = cls._expr_binary(span, "/", 2)
        return cls._expr_binary(center, "-", half_span), cls._expr_binary(center, "+", half_span)

    @classmethod
    def _component_name(cls, parameters: Dict[str, Any]) -> str:
        return cls._sanitize_cst_name(parameters.get("component", cls.DEFAULT_COMPONENT))
    
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
            "create_component": self._create_component,
            "define_brick": self._define_brick,
            "define_sphere": self._define_sphere,
            "define_cone": self._define_cone,
            "define_torus": self._define_torus,
            "define_cylinder": self._define_cylinder,
            "define_ecylinder": self._define_ecylinder,
            "define_extrude": self._define_extrude,
            "define_rotate": self._define_rotate,
            "define_loft": self._define_loft,
            "define_parameter": self._define_parameter,
            "update_parameter": self._update_parameter,
            "rebuild_model": self._rebuild_model,
            "boolean_add": self._boolean_add,
            "boolean_intersect": self._boolean_intersect,
            "boolean_subtract": self._boolean_subtract,
            "boolean_insert": self._boolean_insert,
            "pick_face": self._pick_face,
            "pick_edge": self._pick_edge,
            "pick_endpoint": self._pick_endpoint,
            "calculate_port_extension_coefficient": self._calculate_port_extension_coefficient,
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
            # V2 aliases
            "new_component": self._create_component,
            "brick": self._define_brick,
            "sphere": self._define_sphere,
            "cone": self._define_cone,
            "torus": self._define_torus,
            "cylinder": self._define_cylinder,
            "ecylinder": self._define_ecylinder,
            "extrude": self._define_extrude,
            "rotate": self._define_rotate,
            "loft": self._define_loft,
            "set_parameter": self._update_parameter,
            "solid_add": self._boolean_add,
            "solid_intersect": self._boolean_intersect,
            "solid_subtract": self._boolean_subtract,
            "solid_insert": self._boolean_insert,
            "pick_end_point": self._pick_endpoint,
        }
        handler = dispatch.get(command_type)
        if handler is None:
            raise ValueError(f"Unsupported command type: {command_type}")
        macro_code = handler(parameters)
        logger.debug(f"Generated macro for {command_type}")
        return macro_code

    @classmethod
    def _brick(
        cls,
        name: str,
        component: str,
        material: str,
        x_min: Any,
        x_max: Any,
        y_min: Any,
        y_max: Any,
        z_min: Any,
        z_max: Any,
    ) -> str:
        safe_name = cls._sanitize_cst_name(name)
        safe_component = cls._sanitize_cst_name(component)
        safe_material = cls._sanitize_cst_name(material)
        return f"""
With Brick
    .Reset
    .Name \"{safe_name}\"
    .Component \"{safe_component}\"
    .Material \"{safe_material}\"
    .Xrange \"{cls._format_cst_value(x_min)}\", \"{cls._format_cst_value(x_max)}\"
    .Yrange \"{cls._format_cst_value(y_min)}\", \"{cls._format_cst_value(y_max)}\"
    .Zrange \"{cls._format_cst_value(z_min)}\", \"{cls._format_cst_value(z_max)}\"
    .Create
End With
""".strip()

    def _create_project(self, parameters: Dict[str, Any]) -> str:
        raise ValueError("create_project must be handled by the caller, not emitted as VBA")

    def _create_component(self, parameters: Dict[str, Any]) -> str:
        component_name = self._sanitize_cst_name(parameters.get("component", parameters.get("name", self.DEFAULT_COMPONENT)))
        return f'Component.New "{component_name}"'

    def _define_brick(self, parameters: Dict[str, Any]) -> str:
        return self._brick(
            parameters["name"],
            self._component_name(parameters),
            parameters.get("material", "PEC"),
            parameters["xrange"][0],
            parameters["xrange"][1],
            parameters["yrange"][0],
            parameters["yrange"][1],
            parameters["zrange"][0],
            parameters["zrange"][1],
        )

    def _define_sphere(self, parameters: Dict[str, Any]) -> str:
        name = self._sanitize_cst_name(parameters["name"])
        component = self._component_name(parameters)
        material = self._sanitize_cst_name(parameters.get("material", "PEC"))
        center = parameters["center"]
        segments = parameters.get("segments", 0)
        return f"""
With Sphere
    .Reset
    .Name "{name}"
    .Component "{component}"
    .Material "{material}"
    .Axis "{parameters.get('axis', 'z')}"
    .CenterRadius "{parameters.get('center_radius', 0)}"
    .TopRadius "{parameters.get('top_radius', 0)}"
    .BottomRadius "{parameters.get('bottom_radius', 0)}"
    .Center "{center[0]}", "{center[1]}", "{center[2]}"
    .Segments "{segments}"
    .Create
End With
""".strip()

    def _define_cone(self, parameters: Dict[str, Any]) -> str:
        name = self._sanitize_cst_name(parameters["name"])
        component = self._component_name(parameters)
        material = self._sanitize_cst_name(parameters.get("material", "PEC"))
        zrange = parameters["zrange"]
        return f"""
With Cone
    .Reset
    .Name "{name}"
    .Component "{component}"
    .Material "{material}"
    .BottomRadius "{parameters.get('bottom_radius', 1)}"
    .TopRadius "{parameters.get('top_radius', 0)}"
    .Axis "{parameters.get('axis', 'z')}"
    .Zrange "{zrange[0]}", "{zrange[1]}"
    .Xcenter "{parameters.get('xcenter', 0)}"
    .Ycenter "{parameters.get('ycenter', 0)}"
    .Segments "{parameters.get('segments', 0)}"
    .Create
End With
""".strip()

    def _define_torus(self, parameters: Dict[str, Any]) -> str:
        name = self._sanitize_cst_name(parameters["name"])
        component = self._component_name(parameters)
        material = self._sanitize_cst_name(parameters.get("material", "PEC"))
        center = parameters.get("center", [0, 0, 0])
        return f"""
With Torus
    .Reset
    .Name "{name}"
    .Component "{component}"
    .Material "{material}"
    .OuterRadius "{parameters.get('outer_radius', 1)}"
    .InnerRadius "{parameters.get('inner_radius', 0.5)}"
    .Axis "{parameters.get('axis', 'z')}"
    .Xcenter "{center[0]}"
    .Ycenter "{center[1]}"
    .Zcenter "{center[2]}"
    .Segments "{parameters.get('segments', 0)}"
    .Create
End With
""".strip()

    def _define_cylinder(self, parameters: Dict[str, Any]) -> str:
        name = self._sanitize_cst_name(parameters["name"])
        component = self._component_name(parameters)
        material = self._sanitize_cst_name(parameters.get("material", "PEC"))
        zrange = parameters["zrange"]
        center = parameters.get("center", [0, 0])
        return f"""
With Cylinder
    .Reset
    .Name "{name}"
    .Component "{component}"
    .Material "{material}"
    .OuterRadius "{parameters.get('outer_radius', 1)}"
    .InnerRadius "{parameters.get('inner_radius', 0)}"
    .Axis "{parameters.get('axis', 'z')}"
    .Zrange "{zrange[0]}", "{zrange[1]}"
    .Xcenter "{center[0]}"
    .Ycenter "{center[1]}"
    .Segments "{parameters.get('segments', 0)}"
    .Create
End With
""".strip()

    def _define_ecylinder(self, parameters: Dict[str, Any]) -> str:
        name = self._sanitize_cst_name(parameters["name"])
        component = self._component_name(parameters)
        material = self._sanitize_cst_name(parameters.get("material", "PEC"))
        zrange = parameters["zrange"]
        center = parameters.get("center", [0, 0])
        return f"""
With ECylinder
    .Reset
    .Name "{name}"
    .Component "{component}"
    .Material "{material}"
    .Xradius "{parameters.get('xradius', 1)}"
    .Yradius "{parameters.get('yradius', 1)}"
    .Axis "{parameters.get('axis', 'z')}"
    .Zrange "{zrange[0]}", "{zrange[1]}"
    .Xcenter "{center[0]}"
    .Ycenter "{center[1]}"
    .Segments "{parameters.get('segments', 0)}"
    .Create
End With
""".strip()

    def _pointlist_block(self, points: List[List[Any]], close: bool = False) -> str:
        if not points:
            raise ValueError("Point-list based operation requires at least one point")
        rows = [f'    .Point "{points[0][0]}", "{points[0][1]}"']
        for point in points[1:]:
            rows.append(f'    .LineTo "{point[0]}", "{point[1]}"')
        if close and (points[0][0] != points[-1][0] or points[0][1] != points[-1][1]):
            rows.append(f'    .LineTo "{points[0][0]}", "{points[0][1]}"')
        return "\n".join(rows)

    def _define_extrude(self, parameters: Dict[str, Any]) -> str:
        name = self._sanitize_cst_name(parameters["name"])
        component = self._component_name(parameters)
        material = self._sanitize_cst_name(parameters.get("material", "PEC"))
        origin = parameters.get("origin", [0.0, 0.0, 0.0])
        uvector = parameters.get("uvector", [1.0, 0.0, 0.0])
        vvector = parameters.get("vvector", [0.0, 1.0, 0.0])
        points = parameters.get("points", [])
        pointlist = self._pointlist_block(points, close=True)
        return f"""
With Extrude
    .Reset
    .Name "{name}"
    .Component "{component}"
    .Material "{material}"
    .Mode "{parameters.get('mode', 'Pointlist')}"
    .Height "{parameters.get('height', 1)}"
    .Twist "{parameters.get('twist', 0.0)}"
    .Taper "{parameters.get('taper', 0.0)}"
    .Origin "{origin[0]}", "{origin[1]}", "{origin[2]}"
    .Uvector "{uvector[0]}", "{uvector[1]}", "{uvector[2]}"
    .Vvector "{vvector[0]}", "{vvector[1]}", "{vvector[2]}"
{pointlist}
    .Create
End With
""".strip()

    def _define_rotate(self, parameters: Dict[str, Any]) -> str:
        name = self._sanitize_cst_name(parameters["name"])
        component = self._component_name(parameters)
        material = self._sanitize_cst_name(parameters.get("material", "PEC"))
        origin = parameters.get("origin", [0.0, 0.0, 0.0])
        rvector = parameters.get("rvector", [0.0, 1.0, 0.0])
        zvector = parameters.get("zvector", [1.0, 0.0, 0.0])
        points = parameters.get("points", [])
        pointlist = self._pointlist_block(points, close=True)
        return f"""
With Rotate
    .Reset
    .Name "{name}"
    .Component "{component}"
    .Material "{material}"
    .Mode "{parameters.get('mode', 'Pointlist')}"
    .StartAngle "{parameters.get('start_angle', 0.0)}"
    .Angle "{parameters.get('angle', 360)}"
    .Height "{parameters.get('height', 0.0)}"
    .RadiusRatio "{parameters.get('radius_ratio', 1.0)}"
    .NSteps "{parameters.get('nsteps', 0)}"
    .SplitClosedEdges "{self._to_bool_string(parameters.get('split_closed_edges', True))}"
    .SegmentedProfile "{self._to_bool_string(parameters.get('segmented_profile', False))}"
    .SimplifySolid "{self._to_bool_string(parameters.get('simplify_solid', False))}"
    .UseAdvancedSegmentedRotation "{self._to_bool_string(parameters.get('use_advanced_segmented_rotation', True))}"
    .CutEndOff "{self._to_bool_string(parameters.get('cut_end_off', False))}"
    .Origin "{origin[0]}", "{origin[1]}", "{origin[2]}"
    .Rvector "{rvector[0]}", "{rvector[1]}", "{rvector[2]}"
    .Zvector "{zvector[0]}", "{zvector[1]}", "{zvector[2]}"
{pointlist}
    .Create
End With
""".strip()

    def _define_loft(self, parameters: Dict[str, Any]) -> str:
        name = self._sanitize_cst_name(parameters["name"])
        component = self._component_name(parameters)
        material = self._sanitize_cst_name(parameters.get("material", "PEC"))
        return f"""
With Loft
    .Reset
    .Name "{name}"
    .Component "{component}"
    .Material "{material}"
    .Tangency "{parameters.get('tangency', 0.0)}"
    .Minimizetwist "{self._to_bool_string(parameters.get('minimizetwist', True)).lower()}"
    .CreateNew
End With
""".strip()

    def _define_parameter(self, parameters: Dict[str, Any]) -> str:
        name = self._sanitize_cst_name(parameters["name"])
        value = self._format_cst_value(parameters["value"])
        description = parameters.get("description")
        if description:
            safe_description = str(description).replace('"', "")
            return f'StoreParameterWithDescription "{name}", "{value}", "{safe_description}"'
        return f'StoreParameter "{name}", "{value}"'

    def _update_parameter(self, parameters: Dict[str, Any]) -> str:
        name = self._sanitize_cst_name(parameters["name"])
        value = parameters["value"]
        if isinstance(value, (int, float)):
            return f'StoreDoubleParameter "{name}", {float(value)}'
        return f'StoreParameter "{name}", "{self._format_cst_value(value)}"'

    def _rebuild_model(self, parameters: Dict[str, Any]) -> str:
        if parameters.get("full_history", False):
            return "Rebuild\nFullHistoryRebuild"
        return "Rebuild"

    def _boolean_add(self, parameters: Dict[str, Any]) -> str:
        lhs = self._component_object_name(parameters["component"], parameters["target"])
        rhs = self._component_object_name(parameters["component"], parameters["tool"])
        return f'Solid.Add "{lhs}", "{rhs}"'

    def _boolean_intersect(self, parameters: Dict[str, Any]) -> str:
        lhs = self._component_object_name(parameters["component"], parameters["target"])
        rhs = self._component_object_name(parameters["component"], parameters["tool"])
        return f'Solid.Intersect "{lhs}", "{rhs}"'

    def _boolean_subtract(self, parameters: Dict[str, Any]) -> str:
        lhs = self._component_object_name(parameters["component"], parameters["target"])
        rhs = self._component_object_name(parameters["component"], parameters["tool"])
        return f'Solid.Subtract "{lhs}", "{rhs}"'

    def _boolean_insert(self, parameters: Dict[str, Any]) -> str:
        lhs = self._component_object_name(parameters["component"], parameters["target"])
        rhs = self._component_object_name(parameters["component"], parameters["tool"])
        return f'Solid.Insert "{lhs}", "{rhs}"'

    def _pick_face(self, parameters: Dict[str, Any]) -> str:
        obj = self._component_object_name(parameters["component"], parameters["solid"])
        return f'Pick.PickFaceFromId "{obj}", "{parameters["face_id"]}"'

    def _pick_edge(self, parameters: Dict[str, Any]) -> str:
        obj = self._component_object_name(parameters["component"], parameters["solid"])
        return (
            f'Pick.PickEdgeFromId "{obj}", '
            f'"{parameters["edge_id"]}", "{parameters.get("vertex_id", parameters["edge_id"])}"'
        )

    def _pick_endpoint(self, parameters: Dict[str, Any]) -> str:
        obj = self._component_object_name(parameters["component"], parameters["solid"])
        endpoint_id = parameters.get("endpoint_id", parameters.get("point_id"))
        if endpoint_id is None:
            raise ValueError("pick_endpoint requires endpoint_id or point_id")
        return f'Pick.PickEndpointFromId "{obj}", "{endpoint_id}"'

    def _calculate_port_extension_coefficient(self, parameters: Dict[str, Any]) -> str:
        port_id = int(parameters.get("port_id", 1))
        return f"""
With Port
    .PortNumber "{port_id}"
    .CalculatePortExtensionCoefficient
End With
""".strip()

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
        name = self._sanitize_cst_name(parameters["name"])
        kind = parameters["kind"]
        if kind == "conductor":
            conductivity = parameters.get("conductivity_s_per_m", 5.8e7)
            color = parameters.get("color_rgb", [1, 1, 0])
            if not isinstance(color, (list, tuple)) or len(color) != 3:
                color = [1, 1, 0]
            return f"""
With Material
    .Reset
    .Name \"{name}\"
    .Folder \"\"
    .FrqType \"all\"
    .Type \"Lossy metal\"
    .Sigma \"{conductivity}\"
    .Colour \"{color[0]}\", \"{color[1]}\", \"{color[2]}\"
    .Wireframe \"False\"
    .Transparency \"0\"
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
        x_min, x_max = self._centered_bounds(origin["x"], parameters["width_mm"])
        y_min, y_max = self._centered_bounds(origin["y"], parameters["length_mm"])
        z_min = origin["z"]
        z_max = self._expr_binary(origin["z"], "+", parameters["height_mm"])
        return self._brick(parameters["name"], self._component_name(parameters), parameters["material"], x_min, x_max, y_min, y_max, z_min, z_max)

    def _create_ground_plane(self, parameters: Dict[str, Any]) -> str:
        x_min, x_max = self._centered_bounds(0, parameters["width_mm"])
        y_min, y_max = self._centered_bounds(0, parameters["length_mm"])
        z_min = parameters["z_mm"]
        z_max = self._expr_binary(parameters["z_mm"], "+", parameters["thickness_mm"])
        return self._brick(parameters["name"], self._component_name(parameters), parameters["material"], x_min, x_max, y_min, y_max, z_min, z_max)

    def _create_patch(self, parameters: Dict[str, Any]) -> str:
        center = parameters["center_mm"]
        x_min, x_max = self._centered_bounds(center["x"], parameters["width_mm"])
        y_min, y_max = self._centered_bounds(center["y"], parameters["length_mm"])
        z_min = center["z"]
        z_max = self._expr_binary(center["z"], "+", parameters["thickness_mm"])
        return self._brick(parameters["name"], self._component_name(parameters), parameters["material"], x_min, x_max, y_min, y_max, z_min, z_max)

    def _create_feedline(self, parameters: Dict[str, Any]) -> str:
        start = parameters["start_mm"]
        end = parameters["end_mm"]
        half_width = self._expr_binary(parameters["width_mm"], "/", 2)
        def _safe_min(a: Any, b: Any) -> Any:
            """Sort two bounds correctly for both numeric values and CST parameter expressions.

            Python's built-in min/max uses lexicographic ordering for strings, which gives
            wrong Yrange bounds when the values are CST parameter expressions
            (e.g. min("-patch_l/2", "-sub_l/2") → "-patch_l/2" due to 'p' < 's', but
            mathematically -patch_l/2 > -sub_l/2).  When either value is a non-numeric
            expression, the caller is responsible for passing start as the lower bound;
            we return them unchanged so CST evaluates them in the correct Yrange order.
            """
            if self._is_numeric_value(a) and self._is_numeric_value(b):
                return (min(float(str(a)), float(str(b))), max(float(str(a)), float(str(b))))
            return (a, b)  # caller guarantees a <= b for parameter expressions

        if start["x"] == end["x"] and start["y"] != end["y"]:
            x_min = self._expr_binary(start["x"], "-", half_width)
            x_max = self._expr_binary(start["x"], "+", half_width)
            y_min, y_max = _safe_min(start["y"], end["y"])
        elif start["y"] == end["y"] and start["x"] != end["x"]:
            x_min, x_max = _safe_min(start["x"], end["x"])
            y_min = self._expr_binary(start["y"], "-", half_width)
            y_max = self._expr_binary(start["y"], "+", half_width)
        else:
            xl, xh = _safe_min(start["x"], end["x"])
            yl, yh = _safe_min(start["y"], end["y"])
            x_min = self._expr_binary(xl, "-", half_width)
            x_max = self._expr_binary(xh, "+", half_width)
            y_min = self._expr_binary(yl, "-", half_width)
            y_max = self._expr_binary(yh, "+", half_width)
        z_min = start["z"]
        z_max = self._expr_binary(start["z"], "+", parameters["thickness_mm"])
        return self._brick(parameters["name"], self._component_name(parameters), parameters["material"], x_min, x_max, y_min, y_max, z_min, z_max)

    def _create_port(self, parameters: Dict[str, Any]) -> str:
        p1 = parameters.get("p1_mm") or parameters.get("reference_mm")
        if p1 is None:
            raise ValueError("create_port requires p1_mm or reference_mm")
        p2 = parameters.get("p2_mm") or {"x": p1["x"], "y": p1["y"], "z": p1["z"] + 1.0}
        macro = f"""
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
        if parameters.get("calculate_port_extension", False):
            macro += f"""

With Port
    .PortNumber \"{parameters['port_id']}\"
    .CalculatePortExtensionCoefficient
End With
""".rstrip()
        return macro

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
        raw_name = str(
            parameters.get(
                "monitor_name",
                parameters.get("name", f"farfield (f={frequency_ghz:g})"),
            )
        )
        name = raw_name.replace('"', '""')

        # Default subvolume matches known-good CST macro generated manually.
        subvolume = parameters.get(
            "subvolume",
            {
                "xmin": -31.080615997314,
                "xmax": 31.080615997314,
                "ymin": -33.781352996826,
                "ymax": 33.781352996826,
                "zmin": 0.0,
                "zmax": 5.5418050549924,
            },
        )
        offset = parameters.get(
            "subvolume_offset",
            {"xmin": 10, "xmax": 10, "ymin": 10, "ymax": 10, "zmin": 10, "zmax": 10},
        )

        domain = str(parameters.get("domain", "Frequency"))
        field_type = str(parameters.get("field_type", "Farfield"))
        monitor_value = str(parameters.get("monitor_value", f"{frequency_ghz:g}"))
        export_farfield_source = str(parameters.get("export_farfield_source", False)).lower() == "true"
        use_subvolume = str(parameters.get("use_subvolume", False)).lower() == "true"
        coordinates = str(parameters.get("coordinates", "Structure"))
        inflate_with_offset = str(parameters.get("subvolume_inflate_with_offset", False)).lower() == "true"
        offset_type = str(parameters.get("subvolume_offset_type", "FractionOfWavelength"))
        nearfield = str(parameters.get("enable_nearfield_calculation", True)).lower() == "true"

        return f"""
With Monitor
    .Reset
    .Name "{name}"
    .Domain "{domain}"
    .FieldType "{field_type}"
    .MonitorValue "{monitor_value}"
    .ExportFarfieldSource "{str(export_farfield_source)}"
    .UseSubvolume "{str(use_subvolume)}"
    .Coordinates "{coordinates}"
    .SetSubvolume "{subvolume['xmin']}", "{subvolume['xmax']}", "{subvolume['ymin']}", "{subvolume['ymax']}", "{subvolume['zmin']}", "{subvolume['zmax']}"
    .SetSubvolumeOffset "{offset['xmin']}", "{offset['xmax']}", "{offset['ymin']}", "{offset['ymax']}", "{offset['zmin']}", "{offset['zmax']}"
    .SetSubvolumeInflateWithOffset "{str(inflate_with_offset)}"
    .SetSubvolumeOffsetType "{offset_type}"
    .EnableNearfieldCalculation "{str(nearfield)}"
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
