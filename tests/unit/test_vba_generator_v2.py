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


def test_define_conductor_material_sets_copper_color() -> None:
    gen = VBAGenerator()

    macro = gen.generate_macro(
        "define_material",
        {
            "name": "Copper (annealed)",
            "kind": "conductor",
            "conductivity_s_per_m": 5.8e7,
        },
    )

    assert 'With Material' in macro
    assert '.Type "Lossy metal"' in macro
    assert '.Kappa "5.8e+007"' in macro
    assert '.Rho "8930.0"' in macro
    assert '.Colour "1", "1", "0"' in macro


def test_define_material_uses_gold_library_preset() -> None:
    gen = VBAGenerator()

    macro = gen.generate_macro(
        "define_material",
        {
            "name": "Gold",
            "kind": "conductor",
        },
    )

    assert '.Name "Gold"' in macro
    assert '.Type "Lossy metal"' in macro
    assert '.Sigma "4.561e+007"' in macro
    assert '.Rho "19320.0"' in macro


def test_define_material_uses_silver_library_preset() -> None:
    gen = VBAGenerator()

    macro = gen.generate_macro(
        "define_material",
        {
            "name": "Silver",
            "kind": "conductor",
        },
    )

    assert '.Name "Silver"' in macro
    assert '.Type "Lossy metal"' in macro
    assert '.Sigma "6.3012e007"' in macro
    assert '.Rho "10500.0"' in macro


def test_define_material_treats_lossy_metal_kind_as_conductor() -> None:
    gen = VBAGenerator()

    macro = gen.generate_macro(
        "define_material",
        {
            "name": "CustomMetal",
            "kind": "lossy metal",
            "conductivity_s_per_m": 1.23e6,
        },
    )

    assert '.Type "Lossy metal"' in macro
    assert '.Sigma "1230000.0"' in macro


def test_define_material_uses_fr4_library_preset() -> None:
    gen = VBAGenerator()

    macro = gen.generate_macro(
        "define_material",
        {
            "name": "FR-4 (lossy)",
            "kind": "dielectric",
        },
    )

    assert '.Name "FR-4_(lossy)"' in macro
    assert '.Epsilon "4.3"' in macro
    assert '.TanD "0.025"' in macro
    assert '.SetActiveMaterial "all"' in macro


def test_define_material_uses_rogers_5880_library_preset_with_alias() -> None:
    gen = VBAGenerator()

    macro = gen.generate_macro(
        "define_material",
        {
            "name": "Rogers RT/duroid 5880",
            "kind": "dielectric",
        },
    )

    assert '.Name "Rogers_RT_duroid_5880"' in macro
    assert '.Epsilon "2.2"' in macro
    assert '.TanD "0.0009"' in macro


def test_define_material_uses_rogers_ro3003_library_preset() -> None:
    gen = VBAGenerator()

    macro = gen.generate_macro(
        "define_material",
        {
            "name": "Rogers RO3003 (lossy)",
            "kind": "dielectric",
        },
    )

    assert '.Name "Rogers_RO3003_(lossy)"' in macro
    assert '.Epsilon "3"' in macro
    assert '.TanD "0.0010"' in macro


def test_define_material_uses_rogers_ro4350b_library_preset() -> None:
    gen = VBAGenerator()

    macro = gen.generate_macro(
        "define_material",
        {
            "name": "Rogers RO4350B (lossy)",
            "kind": "dielectric",
        },
    )

    assert '.Name "Rogers_RO4350B_(lossy)"' in macro
    assert '.Epsilon "3.66"' in macro
    assert '.TanD "0.0037"' in macro
