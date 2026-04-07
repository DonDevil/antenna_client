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
