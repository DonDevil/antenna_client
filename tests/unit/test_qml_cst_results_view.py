import importlib.util
import json
from pathlib import Path

import session.session_store as session_store_module


MODULE_PATH = Path(__file__).resolve().parents[2] / "ui" / "main_qml_app.py"
SPEC = importlib.util.spec_from_file_location("qml_main_qml_app_cst_results", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
DesignController = MODULE.DesignController


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _prepare_workspace(monkeypatch, tmp_path: Path) -> Path:
    exports_dir = tmp_path / "artifacts" / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    _write_json(tmp_path / "config.json", {"server": {"base_url": "http://localhost:8000"}})

    session_dir = tmp_path / "test_checkpoints"
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(session_store_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(session_store_module, "SESSION_DIR", session_dir)
    return exports_dir


def _seed_cst_exports(exports_dir: Path) -> None:
    s11_trace_path = _write_text(
        exports_dir / "s11.txt",
        "2.39 -12.0\n2.45 -18.5\n2.51 -11.5\n",
    )
    _write_json(
        exports_dir / "summary_metrics_iter0.json",
        {
            "s11_metrics": {
                "center_frequency": 2.45,
                "bandwidth": 0.12,
                "min_s11_db": -18.5,
                "start_freq": 2.39,
                "stop_freq": 2.51,
            },
            "farfield_metrics": None,
        },
    )

    farfield_summary_path = _write_text(exports_dir / "patch_farfield_summary.txt", "Maximum realized gain [dB]: 5.4\n")
    farfield_theta_cut_path = _write_text(exports_dir / "patch_farfield_theta_cut.txt", "0 0 5.4\n180 0 -8.8\n")
    farfield_source_path = _write_text(exports_dir / "patch_farfield.txt", "theta phi gain\n")
    farfield_metrics_path = exports_dir / "patch_farfield_metrics.json"
    _write_json(
        farfield_metrics_path,
        {
            "main_lobe_direction_deg": 10.0,
            "beamwidth_3db_deg": 48.0,
            "front_to_back_ratio_db": 14.2,
            "max_gain_dbi": 6.1,
            "max_realized_gain_dbi": 5.4,
            "max_directivity_dbi": 6.8,
            "radiation_efficiency_db": -0.9,
            "total_efficiency_db": -1.4,
            "summary_file": str(farfield_summary_path.resolve()),
            "theta_cut_file": str(farfield_theta_cut_path.resolve()),
            "source_file": str(farfield_source_path.resolve()),
            "metrics_file": str(farfield_metrics_path.resolve()),
        },
    )
    _write_json(
        exports_dir / "patch_farfield_meta.json",
        {
            "selected_tree_item": "Farfields\\farfield (f=2.45GHz)",
            "summary_export_path": str(farfield_summary_path.resolve()),
            "theta_cut_export_path": str(farfield_theta_cut_path.resolve()),
            "source_export_path": str(farfield_source_path.resolve()),
        },
    )

    assert s11_trace_path.exists()


def test_current_cst_results_text_reports_metrics_and_artifacts(monkeypatch, tmp_path):
    exports_dir = _prepare_workspace(monkeypatch, tmp_path)
    _seed_cst_exports(exports_dir)

    controller = DesignController()

    payload = json.loads(controller.currentCstResultsText())
    sections = {
        section["title"]: {field["label"]: field["value"] for field in section["fields"]}
        for section in payload["sections"]
    }
    artifacts = {item["label"]: item for item in payload["artifacts"]}

    assert payload["available"] is True
    assert sections["S11 Metrics"]["Center Frequency"] == "2.45 GHz"
    assert sections["S11 Metrics"]["Bandwidth"] == "120.0 MHz"
    assert sections["S11 Metrics"]["Return Loss"] == "18.50 dB"
    assert sections["Far-Field Metrics"]["Maximum Realized Gain"] == "5.40 dBi"
    assert sections["Far-Field Metrics"]["3 dB Beamwidth"] == "48.0 deg"
    assert artifacts["S11 Trace"]["exists"] is True
    assert artifacts["Far-Field Metrics JSON"]["exists"] is True
    assert artifacts["Far-Field Metadata"]["exists"] is True


def test_export_results_includes_cst_results_bundle(monkeypatch, tmp_path):
    exports_dir = _prepare_workspace(monkeypatch, tmp_path)
    _seed_cst_exports(exports_dir)

    controller = DesignController()
    controller.session_id = "session-001"
    controller.trace_id = "trace-001"
    controller.design_id = "design-001"
    controller.current_design = {"antenna_family": "microstrip_patch", "frequency_ghz": 2.45}
    controller.last_result = {
        "actual_frequency": "2.45",
        "actual_bandwidth": "120",
        "gain_db": "5.40",
        "vswr": "1.27",
    }

    controller.exportResults()

    exported_files = sorted(exports_dir.glob("qml_export_*.json"))
    assert len(exported_files) == 1

    exported_payload = json.loads(exported_files[0].read_text(encoding="utf-8"))
    cst_results = exported_payload["cst_results"]
    artifact_labels = {item["label"]: item for item in cst_results["artifacts"]}

    assert cst_results["available"] is True
    assert cst_results["sections"][0]["title"] == "Latest Result Snapshot"
    assert artifact_labels["Far-Field Theta Cut"]["exists"] is True
    assert artifact_labels["S11 Summary Metrics"]["exists"] is True


def test_active_session_prefers_its_own_artifacts_over_latest_global(monkeypatch, tmp_path):
    exports_dir = _prepare_workspace(monkeypatch, tmp_path)

    session_summary_path = _write_json(
        exports_dir / "sessionA_summary_metrics.json",
        {
            "s11_metrics": {
                "center_frequency": 2.41,
                "bandwidth": 0.08,
                "min_s11_db": -12.0,
            },
            "farfield_metrics": None,
        },
    )
    session_s11_path = _write_text(exports_dir / "sessionA_s11.txt", "2.41 -12.0\n")
    session_farfield_metrics_path = _write_json(
        exports_dir / "sessionA_farfield_metrics.json",
        {
            "main_lobe_direction_deg": 25.0,
            "beamwidth_3db_deg": 60.0,
            "max_realized_gain_dbi": 3.2,
        },
    )

    _write_json(
        exports_dir / "sessionB_summary_metrics.json",
        {
            "s11_metrics": {
                "center_frequency": 2.62,
                "bandwidth": 0.18,
                "min_s11_db": -21.0,
            },
            "farfield_metrics": None,
        },
    )
    _write_json(
        exports_dir / "sessionB_farfield_metrics.json",
        {
            "main_lobe_direction_deg": 5.0,
            "beamwidth_3db_deg": 30.0,
            "max_realized_gain_dbi": 8.7,
        },
    )

    controller = DesignController()
    controller.session_id = "session-A"
    controller.trace_id = "trace-A"
    controller.design_id = "design-A"
    controller.iteration_index = 0
    controller.session_store.create_session("req", session_id="session-A", trace_id="trace-A", design_id="design-A")
    controller.session_store.update_session_metadata_map(
        "session-A",
        {
            "cst_artifacts": {
                "summary_metrics_path": str(session_summary_path.resolve()),
                "s11_trace_path": str(session_s11_path.resolve()),
                "farfield_metrics_path": str(session_farfield_metrics_path.resolve()),
            },
            "cst_artifacts_by_iteration": {
                "0": {
                    "summary_metrics_path": str(session_summary_path.resolve()),
                    "s11_trace_path": str(session_s11_path.resolve()),
                    "farfield_metrics_path": str(session_farfield_metrics_path.resolve()),
                }
            },
        },
    )

    payload = json.loads(controller.currentCstResultsText())
    sections = {
        section["title"]: {field["label"]: field["value"] for field in section["fields"]}
        for section in payload["sections"]
    }

    assert sections["S11 Metrics"]["Center Frequency"] == "2.41 GHz"
    assert sections["S11 Metrics"]["Bandwidth"] == "80.0 MHz"
    assert sections["Far-Field Metrics"]["Maximum Realized Gain"] == "3.20 dBi"


def test_feedback_payload_uses_session_artifact_paths(monkeypatch, tmp_path):
    exports_dir = _prepare_workspace(monkeypatch, tmp_path)

    session_summary_path = _write_json(
        exports_dir / "sessionC_summary_metrics.json",
        {
            "s11_metrics": {
                "center_frequency": 2.45,
                "bandwidth": 0.1,
                "min_s11_db": -15.0,
            },
            "farfield_metrics": None,
        },
    )
    session_s11_path = _write_text(exports_dir / "sessionC_s11.txt", "2.45 -15.0\n")
    session_farfield_metrics_path = _write_json(
        exports_dir / "sessionC_farfield_metrics.json",
        {
            "main_lobe_direction_deg": 15.0,
            "beamwidth_3db_deg": 45.0,
            "max_realized_gain_dbi": 4.4,
        },
    )

    controller = DesignController()
    controller.session_id = "session-C"
    controller.trace_id = "trace-C"
    controller.design_id = "design-C"
    controller.iteration_index = 2
    controller.last_result = {
        "actual_frequency": "2.45",
        "actual_bandwidth": "100",
        "gain_db": "4.4",
        "vswr": "1.42",
    }
    controller.session_store.create_session("req", session_id="session-C", trace_id="trace-C", design_id="design-C")
    controller.session_store.update_session_metadata_map(
        "session-C",
        {
            "cst_artifacts": {
                "summary_metrics_path": str(session_summary_path.resolve()),
                "s11_trace_path": str(session_s11_path.resolve()),
                "farfield_metrics_path": str(session_farfield_metrics_path.resolve()),
            },
            "cst_artifacts_by_iteration": {
                "2": {
                    "summary_metrics_path": str(session_summary_path.resolve()),
                    "s11_trace_path": str(session_s11_path.resolve()),
                    "farfield_metrics_path": str(session_farfield_metrics_path.resolve()),
                }
            },
        },
    )

    payload = controller._build_feedback_payload({}, completion_requested=False)
    artifacts = payload["artifacts"]

    assert artifacts["s11_trace_ref"] == str(session_s11_path.resolve())
    assert artifacts["summary_metrics_ref"] == str(session_summary_path.resolve())
    assert artifacts["farfield_ref"] == str(session_farfield_metrics_path.resolve())


def test_extract_payload_clears_stale_farfield_when_current_metrics_missing(monkeypatch, tmp_path):
    exports_dir = _prepare_workspace(monkeypatch, tmp_path)

    summary_metrics_path = _write_json(
        exports_dir / "sessionD_summary_metrics.json",
        {
            "s11_metrics": {
                "center_frequency": 2.45,
                "bandwidth": 0.1,
                "min_s11_db": -14.0,
            },
            "farfield_metrics": None,
        },
    )
    s11_trace_path = _write_text(exports_dir / "sessionD_s11.txt", "2.45 -14.0\n")

    controller = DesignController()
    controller.session_id = "session-D"
    controller.trace_id = "trace-D"
    controller.design_id = "design-D"
    controller.iteration_index = 0
    controller.last_result = {
        "actual_frequency": "2.60",
        "actual_bandwidth": "220",
        "gain_db": "9.9",
        "vswr": "1.11",
        "farfield": "OLD",
    }
    controller.session_store.create_session("req", session_id="session-D", trace_id="trace-D", design_id="design-D")
    controller.session_store.update_session_metadata_map(
        "session-D",
        {
            "cst_artifacts": {
                "summary_metrics_path": str(summary_metrics_path.resolve()),
                "s11_trace_path": str(s11_trace_path.resolve()),
            },
            "cst_artifacts_by_iteration": {
                "0": {
                    "summary_metrics_path": str(summary_metrics_path.resolve()),
                    "s11_trace_path": str(s11_trace_path.resolve()),
                }
            },
        },
    )

    extracted = controller._extract_cst_result_payload()

    assert extracted["actual_frequency"] == "2.45"
    assert extracted["actual_bandwidth"] == "100"
    assert extracted["vswr"] != ""
    assert extracted["gain_db"] == ""
    assert extracted["farfield"] == ""


def test_execution_completion_emits_farfield_error_when_expected_but_missing(monkeypatch, tmp_path):
    _prepare_workspace(monkeypatch, tmp_path)

    controller = DesignController()
    controller.current_command_package = {
        "commands": [
            {"seq": 1, "command": "export_farfield", "params": {}},
            {"seq": 2, "command": "extract_farfield_metrics", "params": {}},
        ]
    }
    controller.last_result = {
        "actual_frequency": "2.45",
        "actual_bandwidth": "100",
    }

    captured_errors: list[str] = []
    controller.errorOccurred.connect(captured_errors.append)
    monkeypatch.setattr(controller, "refreshConnections", lambda: None)

    controller._on_execution_completed(
        {
            "dry_run": False,
            "progress": {"completed": 2, "total": 2},
            "results": [
                {
                    "command_id": "1:export_farfield",
                    "success": True,
                    "output": "Exported far-field data",
                },
                {
                    "command_id": "2:extract_farfield_metrics",
                    "success": True,
                    "output": "No metrics",
                },
            ],
            "artifacts": {},
        }
    )

    assert captured_errors
    assert "Far-field results are missing" in captured_errors[-1]