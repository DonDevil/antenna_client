"""Tests for newly added V2 CST VBA geometry commands."""

from executor.vba_generator import VBAGenerator


def test_define_brick_v2_macro_generation() -> None:
    gen = VBAGenerator()
    macro = gen.generate_macro(
        "define_brick",
        {
            "name": "solid1",
            "component": "component1",
            "material": "PEC",
            "xrange": [-16, -4],
            "yrange": [-3, 2],
            "zrange": [-3, 0],
        },
    )

    assert "With Brick" in macro
    assert '.Name "solid1"' in macro
    assert '.Component "component1"' in macro
    assert '.Xrange "-16.0", "-4.0"' in macro


def test_boolean_and_pick_commands_generate_expected_vba() -> None:
    gen = VBAGenerator()

    add_macro = gen.generate_macro(
        "boolean_add",
        {"component": "component1", "target": "solid1", "tool": "solid2"},
    )
    face_macro = gen.generate_macro(
        "pick_face",
        {"component": "component1", "solid": "solid1", "face_id": 4},
    )

    assert add_macro == 'Solid.Add "component1:solid1", "component1:solid2"'
    assert face_macro == 'Pick.PickFaceFromId "component1:solid1", "4"'


def test_extrude_rotate_require_points() -> None:
    gen = VBAGenerator()

    try:
        gen.generate_macro("define_extrude", {"name": "solid1", "points": []})
        assert False, "Expected ValueError for empty point list"
    except ValueError as exc:
        assert "Point-list based operation requires at least one point" in str(exc)


def test_parameter_commands_generate_expected_vba() -> None:
    gen = VBAGenerator()

    define_macro = gen.generate_macro("define_parameter", {"name": "px", "value": 37})
    update_macro = gen.generate_macro("update_parameter", {"name": "px", "value": 41.5})
    rebuild_macro = gen.generate_macro("rebuild_model", {})

    assert define_macro == 'StoreParameter "px", "37.0"'
    assert update_macro == 'StoreDoubleParameter "px", 41.5'
    assert rebuild_macro == "Rebuild"


def test_create_patch_preserves_component_and_parameter_expressions() -> None:
    gen = VBAGenerator()

    macro = gen.generate_macro(
        "create_patch",
        {
            "name": "patch",
            "component": "antenna",
            "material": "PEC",
            "length_mm": "px",
            "width_mm": "py",
            "thickness_mm": "t_cu",
            "center_mm": {"x": 0, "y": 0, "z": "h_sub"},
        },
    )

    assert '.Component "antenna"' in macro
    assert '.Xrange "(0.0)-((py)/(2.0))", "(0.0)+((py)/(2.0))"' in macro
    assert '.Yrange "(0.0)-((px)/(2.0))", "(0.0)+((px)/(2.0))"' in macro
    assert '.Zrange "h_sub", "(h_sub)+(t_cu)"' in macro


def test_create_port_macro_does_not_calculate_extension_by_default() -> None:
    gen = VBAGenerator()

    macro = gen.generate_macro(
        "create_port",
        {
            "port_id": 1,
            "impedance_ohm": 50.0,
            "p1_mm": {"x": 0.0, "y": -20.0, "z": 1.6},
            "p2_mm": {"x": 0.0, "y": -20.0, "z": 0.035},
        },
    )

    assert 'With DiscretePort' in macro
    assert '.SetP1 "False", "0.0", "-20.0", "1.6"' in macro
    assert '.SetP2 "False", "0.0", "-20.0", "0.035"' in macro
    assert 'CalculatePortExtensionCoefficient' not in macro


def test_create_port_macro_allows_opt_in_extension_calculation() -> None:
    gen = VBAGenerator()

    macro = gen.generate_macro(
        "create_port",
        {
            "port_id": 1,
            "impedance_ohm": 50.0,
            "p1_mm": {"x": 0.0, "y": -20.0, "z": 1.6},
            "p2_mm": {"x": 0.0, "y": -20.0, "z": 0.035},
            "calculate_port_extension": True,
        },
    )

    assert 'CalculatePortExtensionCoefficient' in macro
