import json
from pathlib import Path

from cst_client.cst_app import CSTApp


def test_extract_farfield_metrics_without_theta_cut_returns_partial_metrics(tmp_path):
    summary_file = tmp_path / "ff_summary.txt"
    source_file = tmp_path / "ff_source.txt"
    missing_theta = tmp_path / "ff_theta_cut_missing.txt"

    summary_file.write_text(
        "\n".join(
            [
                "Maximum gain [dB]: 6.25",
                "Maximum realized gain [dB]: 5.75",
                "Maximum directivity [dB]: 7.10",
                "Radiation efficiency: -0.80",
                "Total efficiency: -1.20",
            ]
        ),
        encoding="utf-8",
    )
    source_file.write_text("theta phi gain\n", encoding="utf-8")

    metrics = CSTApp.extract_farfield_metrics_from_files(
        summary_file=str(summary_file),
        theta_cut_file=str(missing_theta),
        source_file=str(source_file),
    )

    assert metrics is not None
    assert metrics["theta_cut_available"] is False
    assert metrics["max_gain_dbi"] == 6.25
    assert metrics["max_realized_gain_dbi"] == 5.75
    assert metrics["max_directivity_dbi"] == 7.10
    assert metrics["beamwidth_3db_deg"] is None
    assert metrics["front_to_back_ratio_db"] is None
    assert "warning" in metrics
