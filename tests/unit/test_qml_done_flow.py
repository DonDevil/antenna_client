import importlib.util
from pathlib import Path

from session.session_store import SessionStore


MODULE_PATH = Path(__file__).resolve().parents[2] / "ui" / "main_qml_app.py"
SPEC = importlib.util.spec_from_file_location("qml_main_qml_app", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
DesignController = MODULE.DesignController


def test_mark_done_uses_feedback_cycle(monkeypatch):
    controller = DesignController()
    captured = {}

    def fake_start_feedback_cycle(feedback_text, completion_requested):
        captured["feedback_text"] = feedback_text
        captured["completion_requested"] = completion_requested

    monkeypatch.setattr(controller, "_start_feedback_cycle", fake_start_feedback_cycle)

    controller.markDone('{"actual_frequency": "2.44"}')

    assert captured["feedback_text"] == '{"actual_frequency": "2.44"}'
    assert captured["completion_requested"] is True


def test_feedback_payload_includes_completion_requested(monkeypatch):
    controller = DesignController()
    controller.session_id = "test-session"
    controller.trace_id = "trace-001"
    controller.design_id = "design-001"
    controller.iteration_index = 2
    controller.last_result = {
        "actual_frequency": "2.44",
        "actual_bandwidth": "98.5",
        "gain_db": "4.6",
        "vswr": "1.48",
    }

    monkeypatch.setattr(controller, "_load_latest_sparam_metrics", lambda: (None, None))
    monkeypatch.setattr(controller, "_load_latest_farfield_metrics", lambda: (None, None))

    payload = controller._build_feedback_payload({}, completion_requested=True)

    assert payload["completion_requested"] is True
    assert payload["iteration_index"] == 2
    assert payload["session_id"] == "test-session"


def test_feedback_response_keeps_session_active_until_server_completion():
    controller = DesignController()
    session = controller.session_store.create_session(
        "Test request",
        session_id="test-session",
        trace_id="trace-001",
        design_id="design-001",
    )
    controller.session_id = session.session_id
    controller.trace_id = session.trace_id
    controller.design_id = session.design_id

    controller._feedback_completion_requested = True
    controller._on_feedback_response_received({
        "status": "refining",
        "accepted": False,
        "message": "Need one more iteration",
    })

    assert controller.session_store.get_session("test-session").status == "active"

    controller._feedback_completion_requested = True
    controller._on_feedback_response_received({
        "status": "completed",
        "accepted": True,
        "stop_reason": "user_marked_done",
        "message": "Session completed by explicit client request.",
    })

    restored = controller.session_store.get_session("test-session")
    assert restored is not None
    assert restored.status == "completed"
    assert controller.current_stage == "user_marked_done"

    controller.session_store.delete_session("test-session")


def test_restore_prefers_metadata_iteration_index():
    controller = DesignController()
    session = controller.session_store.create_session(
        "Test request",
        session_id="test-session",
        trace_id="trace-001",
        design_id="design-001",
    )
    session.current_iteration = 3
    session.metadata["iteration_index"] = 1

    controller._restore_session(session)

    assert controller.iteration_index == 1

    controller.session_store.delete_session("test-session")


def test_store_result_uses_reported_iteration():
    store = SessionStore()
    session = store.create_session(
        "Test request",
        session_id="test-session-store",
        trace_id="trace-001",
        design_id="design-001",
    )

    store.store_result(session.session_id, {"iteration_index": 0, "last_result": {"actual_frequency": "2.44"}})
    assert store.get_session(session.session_id).current_iteration == 0

    store.store_result(session.session_id, {"iteration_index": 1, "last_result": {"actual_frequency": "2.45"}})
    assert store.get_session(session.session_id).current_iteration == 1

    store.delete_session(session.session_id)