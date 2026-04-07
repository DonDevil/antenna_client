from executor.vba_generator import VBAGenerator


def test_add_farfield_monitor_uses_full_manual_template_defaults():
    gen = VBAGenerator()
    macro = gen.generate_macro(
        "add_farfield_monitor",
        {
            "frequency_ghz": 2.45,
            "monitor_name": "farfield (f=2.45)",
        },
    )

    assert '.Name "farfield (f=2.45)"' in macro
    assert '.Domain "Frequency"' in macro
    assert '.FieldType "Farfield"' in macro
    assert '.MonitorValue "2.45"' in macro
    assert '.ExportFarfieldSource "False"' in macro
    assert '.UseSubvolume "False"' in macro
    assert '.Coordinates "Structure"' in macro
    assert '.SetSubvolume "-31.080615997314", "31.080615997314", "-33.781352996826", "33.781352996826", "0.0", "5.5418050549924"' in macro
    assert '.SetSubvolumeOffset "10", "10", "10", "10", "10", "10"' in macro
    assert '.SetSubvolumeInflateWithOffset "False"' in macro
    assert '.SetSubvolumeOffsetType "FractionOfWavelength"' in macro
    assert '.EnableNearfieldCalculation "True"' in macro


def test_add_farfield_monitor_allows_override_parameters():
    gen = VBAGenerator()
    macro = gen.generate_macro(
        "add_farfield_monitor",
        {
            "monitor_name": "my monitor",
            "monitor_value": "2.40",
            "export_farfield_source": True,
            "use_subvolume": True,
            "enable_nearfield_calculation": False,
            "subvolume": {
                "xmin": -10,
                "xmax": 10,
                "ymin": -12,
                "ymax": 12,
                "zmin": 0,
                "zmax": 4,
            },
        },
    )

    assert '.Name "my monitor"' in macro
    assert '.MonitorValue "2.40"' in macro
    assert '.ExportFarfieldSource "True"' in macro
    assert '.UseSubvolume "True"' in macro
    assert '.EnableNearfieldCalculation "False"' in macro
    assert '.SetSubvolume "-10", "10", "-12", "12", "0", "4"' in macro
