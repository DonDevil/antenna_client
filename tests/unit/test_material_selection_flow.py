from __future__ import annotations

from comm.request_builder import RequestBuilder


def test_request_builder_uses_explicit_material_fields() -> None:
    builder = RequestBuilder()

    request = builder.build_optimize_request(
        "Design a microstrip patch antenna at 2.45 GHz",
        design_specs={
            "antenna_family": "microstrip_patch",
            "conductor_material": "Gold",
            "substrate_material": "Rogers RO4350B",
        },
    )

    assert request.design_constraints["allowed_materials"] == ["Gold"]
    assert request.design_constraints["allowed_substrates"] == ["Rogers RO4350B"]


def test_design_panel_round_trips_selected_materials() -> None:
    pytest = __import__("pytest")
    pytest.importorskip("PySide6")

    from PySide6.QtWidgets import QApplication

    from ui.design_panel import DesignPanel

    _ = QApplication.instance() or QApplication([])
    panel = DesignPanel()
    panel.set_supported_materials(
        ["Copper (annealed)", "Silver", "Gold"],
        ["FR-4 (lossy)", "Rogers RT/duroid 5880", "Rogers RO4350B"],
    )

    panel.set_spec_values(
        antenna_family="microstrip_patch",
        conductor_material="Gold",
        substrate_material="Rogers RO4350B",
    )

    specs = panel.get_specs()

    assert specs["conductor_material"] == "Gold"
    assert specs["substrate_material"] == "Rogers RO4350B"
    assert specs["allowed_materials"] == ["Gold"]
    assert specs["allowed_substrates"] == ["Rogers RO4350B"]
