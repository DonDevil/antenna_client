"""QML-Python bridge for the simplified Antenna Design Studio UI."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, QUrl, Signal, Slot
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"

for path in (SRC_ROOT, PROJECT_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from comm.api_client import ApiClient
from comm.response_handler import ResponseHandler
from comm.server_connector import ServerConnector
from cst_client.cst_app import CSTApp
from session.config_manager import ConfigManager
from session.session_store import Session, SessionStore
from utils.chat_message_handler import (
    ChatRequestWorker,
    CommandExecutionWorker,
    FeedbackRequestWorker,
    OptimizeRequestWorker,
)
from utils.connection_checker import ConnectionChecker
from utils.validators import extract_antenna_family


class _AsyncWorker(QThread):
    error_occurred = Signal(str)

    @staticmethod
    def _run_async(coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    @staticmethod
    def _load_base_url() -> str:
        config_path = PROJECT_ROOT / "config.json"
        if not config_path.exists():
            return "http://localhost:8000"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        return config.get("server", {}).get("base_url", "http://localhost:8000")


class ConnectionCheckWorker(_AsyncWorker):
    response_ready = Signal(dict)

    def run(self):
        try:
            result = self._run_async(ConnectionChecker.check_all())
            health = result.get("health", {}) if isinstance(result, dict) else {}
            server_ok, server_msg = result.get("server", (False, "Unavailable"))
            cst_ok, cst_msg = result.get("cst", (False, "Unavailable"))
            payload = {
                "ann_connected": health.get("ann_status") == "available",
                "llm_connected": health.get("llm_status") == "available",
                "cst_connected": bool(cst_ok),
                "comm_connected": bool(server_ok),
                "ann_status": health.get("ann_status", "none"),
                "llm_status": health.get("llm_status", "none"),
                "server_message": server_msg,
                "cst_message": cst_msg,
            }
            self.response_ready.emit(payload)
        except Exception as e:
            self.error_occurred.emit(str(e))


class SessionFetchWorker(_AsyncWorker):
    response_ready = Signal(dict)

    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id

    def run(self):
        try:
            payload = self._run_async(self._fetch_async())
            self.response_ready.emit(payload)
        except Exception as e:
            self.error_occurred.emit(str(e))

    async def _fetch_async(self) -> dict[str, Any]:
        base_url = self._load_base_url()
        async with ServerConnector(base_url, timeout_sec=20) as connector:
            api = ApiClient(connector)
            return await api.get_session(self.session_id)


class DesignController(QObject):
    """Bridge between QML and Python/backend workflow."""

    chatMessageReceived = Signal(str, str)
    designUpdated = Signal(dict)
    resultReceived = Signal(dict)
    errorOccurred = Signal(str)
    statusChanged = Signal(str)
    sessionRestored = Signal(str)
    connectionStatusChanged = Signal(dict)

    def __init__(self):
        super().__init__()
        self.session_store = SessionStore()
        self.config_manager = ConfigManager(str(PROJECT_ROOT / "config.json"))
        self.response_handler = ResponseHandler()
        self.current_design: dict[str, Any] = {}
        self.chat_history: list[dict[str, str]] = []
        self.last_result: dict[str, str] = {}
        self.session_id: str | None = None
        self.trace_id: str | None = None
        self.design_id: str | None = None
        self.session_name: str = ""
        self.iteration_index: int = 0
        self.current_command_package: dict[str, Any] | None = None
        self.current_stage: str = "idle"
        self.current_worker: QThread | None = None
        self.connection_worker: QThread | None = None
        self.session_fetch_worker: QThread | None = None
        self._feedback_completion_requested = False
        self._is_shutting_down = False

    @Slot()
    def refreshConnections(self):
        worker = ConnectionCheckWorker()
        worker.response_ready.connect(self._on_connection_status_received)
        worker.error_occurred.connect(self._on_worker_error)
        self._start_worker("connection_worker", worker)

    @Slot(str, str)
    def sendChatMessage(self, message: str, chatMode: str):
        message = str(message or "").strip()
        if not message:
            return

        self.chat_history.append({"sender": "You", "message": message})
        self.chatMessageReceived.emit("You", message)
        self.statusChanged.emit(f"Sending message ({chatMode} mode)...")

        worker = ChatRequestWorker(message, self.current_design.copy(), chat_mode=chatMode)
        worker.response_ready.connect(self._on_chat_response_received)
        worker.error_occurred.connect(self._on_worker_error)
        self._start_worker("current_worker", worker)

    @Slot(str)
    def updateDesignParameter(self, parameters: str):
        try:
            params = json.loads(parameters)
            normalized = dict(params)
            family = self._normalize_antenna_family(normalized.get("antenna_family"))
            if family:
                normalized["antenna_family"] = family
            self.current_design.update(normalized)
            self.designUpdated.emit(self.current_design)
            self._persist_runtime_snapshot()
            self.statusChanged.emit("Design parameters updated")
        except Exception as e:
            self.errorOccurred.emit(f"Failed to update parameters: {e}")

    @Slot()
    def startDesign(self):
        specs = self._build_design_specs()
        if not specs.get("antenna_family"):
            self.errorOccurred.emit("Antenna family is required before starting")
            return

        user_request = self._build_pipeline_request_text()
        self.statusChanged.emit("Sending optimize request to server...")
        self.current_worker = OptimizeRequestWorker(user_request, specs, self.session_id)
        self.current_worker.response_ready.connect(self._on_optimize_response_received)
        self.current_worker.error_occurred.connect(self._on_worker_error)
        self.current_worker.start()

    @Slot(str)
    def submitFeedback(self, feedbackText: str):
        self._start_feedback_cycle(feedbackText, completion_requested=False)

    @Slot(str)
    def markDone(self, feedbackText: str):
        if not self.session_id:
            self.errorOccurred.emit("Active session required before completing")
            return

        try:
            payload = json.loads(feedbackText or "{}")
        except json.JSONDecodeError as e:
            self.errorOccurred.emit(f"Invalid completion payload: {e}")
            return

        self._merge_feedback_values_into_last_result(payload)
        self.current_stage = "completed"
        self.current_command_package = None
        self._feedback_completion_requested = False
        self.session_store.update_session_status(self.session_id, "completed")
        self.chat_history.append({"sender": "System", "message": "Session marked complete from the QML UI."})
        self.chatMessageReceived.emit("System", "Session marked complete from the QML UI.")
        self.resultReceived.emit(self.last_result or self._empty_result_payload())
        self.statusChanged.emit("Session completed.")
        self._persist_runtime_snapshot()

    @Slot()
    def clearDesign(self):
        self.current_design = {}
        self.chat_history = []
        self.last_result = {}
        self.session_id = None
        self.trace_id = None
        self.design_id = None
        self.session_name = ""
        self.iteration_index = 0
        self.current_command_package = None
        self.current_stage = "idle"
        self.designUpdated.emit({})
        self.resultReceived.emit(self._empty_result_payload())
        self.statusChanged.emit("Design cleared")

    @Slot(str)
    def saveCurrentSession(self, sessionName: str):
        try:
            session_name = str(sessionName or self.session_name).strip()
            if not session_name:
                self.errorOccurred.emit("Session name is required")
                return

            self.session_name = session_name
            user_request = next(
                (
                    item["message"]
                    for item in reversed(self.chat_history)
                    if item.get("sender") == "You" and item.get("message")
                ),
                self._build_pipeline_request_text() or "Manual QML session save",
            )
            session = self.session_store.create_session(
                user_request=user_request,
                session_id=self.session_id,
                trace_id=self.trace_id,
                design_id=self.design_id,
            )
            self.session_id = session.session_id
            self._persist_runtime_snapshot()
            self.statusChanged.emit(f"Session saved: {self.session_name}")
        except Exception as e:
            self.errorOccurred.emit(str(e))

    @Slot(str)
    def setSessionName(self, sessionName: str):
        name = str(sessionName or "").strip()
        self.session_name = name
        if self.session_id:
            self._persist_runtime_snapshot()

    @Slot(result=str)
    def currentSessionName(self) -> str:
        return self.session_name

    @Slot(result=str)
    def currentStateText(self) -> str:
        state = {
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "design_id": self.design_id,
            "session_name": self.session_name,
            "iteration_index": self.iteration_index,
            "current_stage": self.current_stage,
            "current_design": self.current_design,
            "chat_history": self.chat_history,
            "last_result": self.last_result,
            "current_command_package": self.current_command_package,
        }
        return json.dumps(state, indent=2)

    @Slot()
    def restoreLatestSession(self):
        sessions = self.session_store.list_sessions()
        if not sessions:
            self.statusChanged.emit("No saved sessions available")
            return
        latest = max(sessions, key=lambda item: item.get("updated_at", ""))
        session = self.session_store.get_session(str(latest.get("session_id", "")))
        if not session:
            self.errorOccurred.emit("Latest session could not be restored")
            return
        self._restore_session(session)
        self.statusChanged.emit(f"Restored latest session: {session.session_id}")

    @Slot(str)
    def continueSessionById(self, sessionId: str):
        session_id = str(sessionId or "").strip()
        if not session_id:
            self.errorOccurred.emit("Session ID is required")
            return

        local_session = self.session_store.get_session(session_id)
        if local_session:
            self._restore_session(local_session)

        self.statusChanged.emit(f"Loading session {session_id} from server...")
        worker = SessionFetchWorker(session_id)
        worker.response_ready.connect(self._on_session_fetch_received)
        worker.error_occurred.connect(self._on_worker_error)
        self._start_worker("session_fetch_worker", worker)

    @Slot(str)
    def restoreSessionFromHistory(self, sessionId: str):
        session_id = str(sessionId or "").strip()
        if not session_id:
            self.errorOccurred.emit("Session ID is required")
            return

        session = self.session_store.get_session(session_id)
        if not session:
            self.errorOccurred.emit(f"Session {session_id} could not be found in local history")
            return

        self._restore_session(session)
        self.statusChanged.emit(f"Restored session: {session_id}")

    @Slot(str, bool)
    def setSessionArchived(self, sessionId: str, archived: bool):
        session_id = str(sessionId or "").strip()
        if not session_id:
            self.errorOccurred.emit("Session ID is required")
            return

        session = self.session_store.get_session(session_id)
        if not session:
            self.errorOccurred.emit(f"Session {session_id} could not be found in local history")
            return

        metadata = dict(session.metadata or {})
        previous_status = str(metadata.get("workflow_status_before_archive") or session.status or "active")

        if archived:
            if session.status and session.status != "archived":
                previous_status = str(session.status)
            metadata["is_archived"] = True
            metadata["workflow_status_before_archive"] = previous_status
            if session.status == "archived":
                self.session_store.update_session_status(session_id, previous_status)
            action_text = "Archived"
        else:
            metadata["is_archived"] = False
            restored_status = str(metadata.get("workflow_status_before_archive") or "active")
            if session.status == "archived":
                self.session_store.update_session_status(session_id, restored_status)
            action_text = "Unarchived"

        self.session_store.update_session_metadata_map(session_id, metadata)
        if self.session_id == session_id:
            self._persist_runtime_snapshot()
        self.statusChanged.emit(f"{action_text} session: {session_id}")

    @Slot(str)
    def deleteSessionFromHistory(self, sessionId: str):
        session_id = str(sessionId or "").strip()
        if not session_id:
            self.errorOccurred.emit("Session ID is required")
            return

        was_active = self.session_id == session_id
        deleted = self.session_store.delete_session(session_id)
        if not deleted:
            self.errorOccurred.emit(f"Session {session_id} could not be deleted")
            return

        if was_active:
            self.clearDesign()
            self.statusChanged.emit(f"Deleted active session: {session_id}")
        else:
            self.statusChanged.emit(f"Deleted session: {session_id}")

    @Slot(result=str)
    def historyDetails(self) -> str:
        session_rows = sorted(
            self.session_store.list_sessions(),
            key=lambda item: item.get("updated_at", ""),
            reverse=True,
        )

        history_items: list[dict[str, Any]] = []
        for row in session_rows:
            session_id = str(row.get("session_id") or "").strip()
            if not session_id:
                continue
            session = self.session_store.get_session(session_id)
            if session is None:
                continue
            history_items.append(self._build_history_item(session))

        return json.dumps(history_items)

    @Slot(result=str)
    def loadConfigText(self) -> str:
        self.config_manager = ConfigManager(str(PROJECT_ROOT / "config.json"))
        return json.dumps(self.config_manager.config, indent=2)

    @Slot(str)
    def saveConfigText(self, configText: str):
        try:
            config_payload = json.loads(configText)
            self.config_manager.config = config_payload
            if self.config_manager.save():
                self.statusChanged.emit("Config saved")
                self.refreshConnections()
            else:
                self.errorOccurred.emit("Failed to save config")
        except json.JSONDecodeError as e:
            self.errorOccurred.emit(f"Invalid config JSON: {e}")

    @Slot()
    def restartApplication(self):
        try:
            subprocess.Popen([sys.executable, str(Path(__file__).resolve())], cwd=str(PROJECT_ROOT))
            self.statusChanged.emit("Restarting UI...")
            self.shutdown()
            app = QApplication.instance()
            if app is not None:
                app.quit()
        except Exception as e:
            self.errorOccurred.emit(f"Failed to restart UI: {e}")

    @Slot()
    def shutdown(self):
        if self._is_shutting_down:
            return

        self._is_shutting_down = True
        if self.session_id:
            self._persist_runtime_snapshot()

        for attr_name in ("current_worker", "connection_worker", "session_fetch_worker"):
            self._stop_worker(attr_name)

    @Slot()
    def exportResults(self):
        try:
            from session.design_exporter import DesignExporter

            exporter = DesignExporter()
            export_dir = PROJECT_ROOT / "artifacts" / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            export_path = export_dir / f"qml_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            payload = {
                "session_id": self.session_id,
                "trace_id": self.trace_id,
                "design_id": self.design_id,
                "design": self.current_design,
                "result": self.last_result,
                "chat_history": self.chat_history,
                "current_command_package": self.current_command_package,
            }
            if exporter.export_to_json(payload, str(export_path)):
                self.statusChanged.emit(f"Results exported: {export_path.name}")
            else:
                self.errorOccurred.emit("Failed to export results")
        except Exception as e:
            self.errorOccurred.emit(str(e))

    def _on_connection_status_received(self, payload: dict[str, Any]):
        self.connectionStatusChanged.emit(payload)
        self.statusChanged.emit(payload.get("server_message") or "Connection status updated")

    def _on_chat_response_received(self, payload: dict[str, Any]):
        requirements = payload.get("requirements", {}) or {}
        if requirements:
            requirements = dict(requirements)
            family = self._normalize_antenna_family(requirements.get("antenna_family"))
            if family:
                requirements["antenna_family"] = family
            self.current_design.update(requirements)
            self.designUpdated.emit(self.current_design)

        assistant_message = payload.get("assistant_message", "Requirements updated.")
        self.chat_history.append({"sender": "Assistant", "message": assistant_message})
        self.chatMessageReceived.emit("Assistant", assistant_message)

        endpoint = payload.get("endpoint_name", "unknown")
        elapsed_ms = payload.get("elapsed_ms")
        if isinstance(elapsed_ms, (int, float)):
            self.statusChanged.emit(f"Chat via {endpoint} in {elapsed_ms:.0f} ms")
        else:
            self.statusChanged.emit("Chat processed")
        self._persist_runtime_snapshot()

    def _on_optimize_response_received(self, response_data: dict[str, Any]):
        try:
            optimize_response = self.response_handler.parse_optimize_response(response_data)
        except Exception as e:
            self.errorOccurred.emit(f"Invalid optimize response: {e}")
            return

        self.session_id = optimize_response.session_id or self.session_id
        self.trace_id = optimize_response.trace_id or self.trace_id
        self.current_stage = optimize_response.current_stage or optimize_response.status
        self.current_command_package = optimize_response.command_package
        self.iteration_index = int((optimize_response.command_package or {}).get("iteration_index", 0))
        self.design_id = (optimize_response.command_package or {}).get("design_id") or self.design_id

        ann_payload = self._ann_prediction_payload(optimize_response)
        if ann_payload:
            self.last_result.update(ann_payload)
            self.resultReceived.emit(self.last_result)

        summary = self._format_optimize_summary(optimize_response)
        self.chat_history.append({"sender": "Assistant", "message": summary})
        self.chatMessageReceived.emit("Assistant", summary)

        self._ensure_runtime_session()
        if self.current_command_package and self.session_id:
            self.session_store.store_command_package(self.session_id, self.current_command_package)
            self.session_store.update_session_status(self.session_id, "active")
            self.statusChanged.emit("ANN prediction received. Executing CST command package...")
            worker = CommandExecutionWorker(self.current_command_package)
            worker.response_ready.connect(self._on_execution_completed)
            worker.error_occurred.connect(self._on_worker_error)
            self._start_worker("current_worker", worker)
        elif self.current_command_package:
            self.statusChanged.emit("Command package received without a session id")
        else:
            self.statusChanged.emit("Optimize request completed without a command package")
        self._persist_runtime_snapshot()

    def _on_execution_completed(self, payload: dict[str, Any]):
        dry_run = bool(payload.get("dry_run", True))
        progress = payload.get("progress", {}) or {}
        extracted = self._extract_cst_result_payload()
        if extracted:
            self.last_result.update(extracted)
            self.resultReceived.emit(self.last_result)

        if self.session_id:
            self.session_store.store_result(
                self.session_id,
                {
                    "iteration_index": self.iteration_index,
                    "dry_run": dry_run,
                    "progress": progress,
                    "last_result": dict(self.last_result),
                },
            )

        completed = progress.get("completed", 0)
        total = progress.get("total", 0)
        status_text = "Command package prepared (dry-run)." if dry_run else "Simulation finished; CST metrics extracted."
        self.chat_history.append({"sender": "Assistant", "message": f"{status_text} Completed {completed}/{total}."})
        self.chatMessageReceived.emit("Assistant", f"{status_text} Completed {completed}/{total}.")
        self.statusChanged.emit(status_text)
        self._persist_runtime_snapshot()
        self.refreshConnections()

    def _start_feedback_cycle(self, feedbackText: str, completion_requested: bool):
        try:
            payload = json.loads(feedbackText or "{}")
        except json.JSONDecodeError as e:
            self.errorOccurred.emit(f"Invalid feedback payload: {e}")
            return

        if not self.session_id or not self.trace_id or not self.design_id:
            self.errorOccurred.emit("Active session required before sending feedback")
            return

        self._feedback_completion_requested = completion_requested
        try:
            request_payload = self._build_feedback_payload(payload, completion_requested)
        except Exception as e:
            self.errorOccurred.emit(str(e))
            return

        label = "done" if completion_requested else "feedback"
        self.statusChanged.emit(f"Submitting {label} to server...")
        worker = FeedbackRequestWorker(request_payload)
        worker.response_ready.connect(self._on_feedback_response_received)
        worker.error_occurred.connect(self._on_worker_error)
        self._start_worker("current_worker", worker)

    def _on_feedback_response_received(self, response_data: dict[str, Any]):
        status = str(response_data.get("status", "unknown"))
        accepted = bool(response_data.get("accepted", False))
        self.chat_history.append({"sender": "Assistant", "message": f"Server feedback response: {status} (accepted={accepted})."})
        self.chatMessageReceived.emit("Assistant", f"Server feedback response: {status} (accepted={accepted}).")

        if self.session_id:
            self.session_store.update_session_status(self.session_id, "completed" if status == "completed" or self._feedback_completion_requested else "active")

        next_package = response_data.get("next_command_package")
        if next_package and not self._feedback_completion_requested:
            self.current_command_package = next_package
            self.iteration_index = int(next_package.get("iteration_index", self.iteration_index + 1))
            self.design_id = next_package.get("design_id", self.design_id)
            if self.session_id:
                self.session_store.store_command_package(self.session_id, next_package)
            self.statusChanged.emit("Server returned refinement commands; executing next iteration...")
            worker = CommandExecutionWorker(next_package)
            worker.response_ready.connect(self._on_execution_completed)
            worker.error_occurred.connect(self._on_worker_error)
            self._start_worker("current_worker", worker)
        else:
            final_status = "Session completed." if self._feedback_completion_requested else "Feedback processed."
            self.statusChanged.emit(final_status)
        self._persist_runtime_snapshot()

    def _on_session_fetch_received(self, session_payload: dict[str, Any]):
        session_id = str(session_payload.get("session_id") or "").strip()
        if not session_id:
            self.errorOccurred.emit("Server did not return a valid session id")
            return

        self.session_id = session_id
        self.current_stage = str(session_payload.get("current_stage") or session_payload.get("status") or self.current_stage)
        self.iteration_index = int(session_payload.get("current_iteration") or self.iteration_index)
        if session_payload.get("trace_id"):
            self.trace_id = str(session_payload.get("trace_id"))
        command_package = session_payload.get("command_package")
        if isinstance(command_package, dict):
            self.current_command_package = command_package
            self.design_id = str(command_package.get("design_id") or self.design_id or "") or None

        self.chat_history.append({
            "sender": "System",
            "message": f"Connected to session {session_id} (status={session_payload.get('status', 'unknown')}, iteration={self.iteration_index}).",
        })
        self.chatMessageReceived.emit(
            "System",
            f"Connected to session {session_id} (status={session_payload.get('status', 'unknown')}, iteration={self.iteration_index}).",
        )
        self.statusChanged.emit(f"Continuing session {session_id}")
        self._persist_runtime_snapshot()
        self.sessionRestored.emit(json.dumps(self._runtime_state_payload()))

    def _on_worker_error(self, error: str):
        if self._is_shutting_down:
            return
        self.errorOccurred.emit(str(error))
        self.statusChanged.emit("Operation failed")
        self.refreshConnections()

    def _start_worker(self, attr_name: str, worker: QThread):
        self._stop_worker(attr_name, wait_only_finished=True)
        setattr(self, attr_name, worker)
        worker.finished.connect(lambda attr=attr_name, thread=worker: self._clear_worker_ref(attr, thread))
        worker.start()

    def _clear_worker_ref(self, attr_name: str, worker: QThread):
        if getattr(self, attr_name) is worker:
            setattr(self, attr_name, None)
        worker.deleteLater()

    def _stop_worker(self, attr_name: str, wait_only_finished: bool = False):
        worker = getattr(self, attr_name)
        if worker is None:
            return

        if worker.isRunning() and not wait_only_finished:
            worker.requestInterruption()
            worker.quit()
            if not worker.wait(2000):
                worker.terminate()
                worker.wait(1000)

        if not worker.isRunning():
            setattr(self, attr_name, None)
            worker.deleteLater()

    def _build_design_specs(self) -> dict[str, Any]:
        family = self._normalize_antenna_family(self.current_design.get("antenna_family"))
        return {
            "antenna_family": family,
            "frequency_ghz": float(self.current_design.get("frequency_ghz") or 2.45),
            "bandwidth_mhz": float(self.current_design.get("bandwidth_mhz") or 100.0),
            "constraints": {
                "max_vswr": float(self.current_design.get("max_vswr") or 2.0),
                "target_gain_dbi": float(self.current_design.get("target_gain_dbi") or 0.0),
            },
        }

    def _build_pipeline_request_text(self) -> str:
        last_user_message = next(
            (
                item["message"]
                for item in reversed(self.chat_history)
                if item.get("sender") == "You" and item.get("message")
            ),
            "",
        )
        family = self._normalize_antenna_family(self.current_design.get("antenna_family")) or "microstrip_patch"
        frequency = float(self.current_design.get("frequency_ghz") or 2.45)
        bandwidth = float(self.current_design.get("bandwidth_mhz") or 100.0)
        if last_user_message:
            return (
                f"{last_user_message}\n\n"
                f"Confirmed desktop fields: family={family}, frequency_ghz={frequency}, bandwidth_mhz={bandwidth}."
            )
        return f"Design a {family} antenna at {frequency} GHz with {bandwidth} MHz bandwidth."

    def _normalize_antenna_family(self, family: Any) -> str | None:
        if family is None:
            return None
        text = str(family).strip()
        if not text:
            return None
        if text in {"amc_patch", "microstrip_patch", "wban_patch"}:
            return text
        return extract_antenna_family(text) or text

    def _ensure_runtime_session(self):
        if not self.session_id:
            return
        existing = self.session_store.get_session(self.session_id)
        if existing is None:
            self.session_store.create_session(
                user_request=self._build_pipeline_request_text(),
                session_id=self.session_id,
                trace_id=self.trace_id,
                design_id=self.design_id,
            )
        else:
            self.session_store.update_session_metadata(
                self.session_id,
                trace_id=self.trace_id,
                design_id=self.design_id,
            )

    def _persist_runtime_snapshot(self):
        if not self.session_id:
            return
        self._ensure_runtime_session()
        metadata = {
            "current_design": dict(self.current_design),
            "chat_history": list(self.chat_history),
            "last_result": dict(self.last_result),
            "session_name": self.session_name,
            "trace_id": self.trace_id,
            "design_id": self.design_id,
            "iteration_index": self.iteration_index,
            "current_stage": self.current_stage,
            "command_package": self.current_command_package,
        }
        self.session_store.update_session_metadata_map(self.session_id, metadata)

    def _merge_feedback_values_into_last_result(self, values: dict[str, Any]):
        if not isinstance(values, dict):
            return

        field_map = {
            "actual_frequency": "actual_frequency",
            "actual_bandwidth": "actual_bandwidth",
            "actual_gain": "gain_db",
            "actual_vswr": "vswr",
            "farfield": "farfield",
        }

        for source_key, target_key in field_map.items():
            value = values.get(source_key)
            if value not in (None, ""):
                self.last_result[target_key] = str(value)

    def _restore_session(self, session: Session):
        metadata = session.metadata or {}
        self.session_id = session.session_id
        self.trace_id = session.trace_id
        self.design_id = session.design_id
        self.session_name = str((session.metadata or {}).get("session_name") or "")
        self.iteration_index = int(session.current_iteration or metadata.get("iteration_index", 0))
        self.current_stage = str(session.status or metadata.get("current_stage", "recovered"))
        self.current_command_package = metadata.get("command_package") or session.command_package
        self.current_design = dict(metadata.get("current_design", {}))
        self.chat_history = list(metadata.get("chat_history", []))
        self.last_result = dict(metadata.get("last_result", {}))
        self.designUpdated.emit(self.current_design)
        self.resultReceived.emit(self.last_result or self._empty_result_payload())
        self.sessionRestored.emit(json.dumps(self._runtime_state_payload()))

    def _runtime_state_payload(self) -> dict[str, Any]:
        return {
            "design": self.current_design,
            "chat_history": self.chat_history,
            "result": self.last_result,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "design_id": self.design_id,
            "session_name": self.session_name,
            "iteration_index": self.iteration_index,
            "current_stage": self.current_stage,
        }

    def _build_history_item(self, session: Session) -> dict[str, Any]:
        metadata = session.metadata if isinstance(session.metadata, dict) else {}
        design_data = metadata.get("current_design")
        design = design_data if isinstance(design_data, dict) else {}
        chat_history_data = metadata.get("chat_history")
        chat_history = chat_history_data if isinstance(chat_history_data, list) else []
        last_result_data = metadata.get("last_result")
        last_result = last_result_data if isinstance(last_result_data, dict) else {}
        if not last_result and session.results:
            latest_result = session.results[-1]
            if isinstance(latest_result, dict):
                nested_last_result = latest_result.get("last_result")
                if isinstance(nested_last_result, dict):
                    last_result = nested_last_result
                else:
                    last_result = latest_result

        command_package = session.command_package if isinstance(session.command_package, dict) else {}
        command_list = command_package.get("commands")
        commands = command_list if isinstance(command_list, list) else []
        session_name = str(metadata.get("session_name") or "").strip()
        is_archived = bool(metadata.get("is_archived")) or str(session.status or "").strip().lower() == "archived"
        family = self._label_text(design.get("antenna_family"))
        frequency = self._format_measurement(design.get("frequency_ghz"), "GHz", decimals=2)
        bandwidth = self._format_measurement(design.get("bandwidth_mhz"), "MHz", decimals=0)
        summary_parts = [part for part in (family, frequency, bandwidth) if part]
        summary_line = " | ".join(summary_parts)
        heading = session_name or summary_line or f"Session {self._short_session_id(session.session_id)}"
        preview_line = summary_line if session_name and summary_line else self._preview_text(session.user_request, limit=120)

        return {
            "session_id": session.session_id,
            "session_short_id": self._short_session_id(session.session_id),
            "session_name": session_name,
            "heading": heading,
            "request_preview": preview_line,
            "user_request": str(session.user_request or ""),
            "status_label": self._label_text(session.status),
            "is_active": session.session_id == self.session_id,
            "is_archived": is_archived,
            "updated_label": self._format_timestamp(session.updated_at),
            "created_label": self._format_timestamp(session.created_at),
            "current_stage": self._label_text(metadata.get("current_stage") or session.status),
            "iteration_count": int(session.current_iteration or metadata.get("iteration_index") or 0),
            "chat_count": len(chat_history),
            "result_count": len(session.results),
            "command_count": len(commands),
            "trace_id": str(session.trace_id or metadata.get("trace_id") or ""),
            "design_id": str(session.design_id or metadata.get("design_id") or ""),
            "actual_frequency": self._format_measurement(last_result.get("actual_frequency"), "GHz", decimals=2),
            "actual_bandwidth": self._format_measurement(last_result.get("actual_bandwidth"), "MHz", decimals=0),
            "actual_gain": self._format_measurement(last_result.get("gain_db"), "dBi", decimals=2),
            "actual_vswr": self._format_measurement(last_result.get("vswr"), "", decimals=2),
            "search_blob": self._history_search_blob(
                session.session_id,
                session_name,
                heading,
                preview_line,
                session.user_request,
                session.status,
                design.get("antenna_family"),
                session.trace_id,
                session.design_id,
            ),
        }

    def _ann_prediction_payload(self, optimize_response) -> dict[str, str]:
        if optimize_response.ann_prediction:
            dims = optimize_response.ann_prediction.dimensions
            return {
                "patch_width": f"{dims.patch_width_mm:.2f}",
                "patch_length": f"{dims.patch_length_mm:.2f}",
                "substrate_width": f"{dims.substrate_width_mm:.2f}",
                "substrate_length": f"{dims.substrate_length_mm:.2f}",
                "feed_width": f"{dims.feed_width_mm:.2f}",
                "feed_length": f"{dims.feed_length_mm:.2f}",
            }

        predicted_dims = (optimize_response.command_package or {}).get("predicted_dimensions", {})
        if not isinstance(predicted_dims, dict):
            return {}
        return {
            "patch_width": self._fmt_number(predicted_dims.get("patch_width_mm")),
            "patch_length": self._fmt_number(predicted_dims.get("patch_length_mm")),
            "substrate_width": self._fmt_number(predicted_dims.get("substrate_width_mm")),
            "substrate_length": self._fmt_number(predicted_dims.get("substrate_length_mm")),
            "feed_width": self._fmt_number(predicted_dims.get("feed_width_mm")),
            "feed_length": self._fmt_number(predicted_dims.get("feed_length_mm")),
        }

    def _format_optimize_summary(self, optimize_response) -> str:
        lines = [f"Server status: {optimize_response.status}."]
        if optimize_response.ann_prediction:
            confidence = int(optimize_response.ann_prediction.confidence * 100)
            lines.append(f"ANN prediction ready (confidence {confidence}%).")
        if optimize_response.command_package:
            lines.append(f"Command package contains {len(optimize_response.command_package.get('commands', []))} CST commands.")
        if optimize_response.session_id:
            lines.append(f"Session ID: {optimize_response.session_id}")
        return " ".join(lines)

    @staticmethod
    def _fmt_number(value: Any) -> str:
        try:
            if value is None:
                return ""
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return str(value or "")

    @staticmethod
    def _label_text(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return text.replace("_", " ").title()

    @staticmethod
    def _preview_text(value: Any, limit: int = 120) -> str:
        text = " ".join(str(value or "").split())
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 3)].rstrip() + "..."

    @staticmethod
    def _short_session_id(session_id: str) -> str:
        text = str(session_id or "").strip()
        if len(text) <= 14:
            return text
        return f"{text[:8]}...{text[-4:]}"

    @staticmethod
    def _format_timestamp(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        try:
            return datetime.fromisoformat(text).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return text

    @staticmethod
    def _format_measurement(value: Any, unit: str, decimals: int = 2) -> str:
        if value in (None, ""):
            return ""

        try:
            formatted = f"{float(value):.{decimals}f}"
        except (TypeError, ValueError):
            formatted = str(value).strip()

        return f"{formatted} {unit}".strip()

    @staticmethod
    def _history_search_blob(*parts: Any) -> str:
        return " ".join(str(part or "").strip().lower() for part in parts if str(part or "").strip())

    @staticmethod
    def _load_json_file(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _load_latest_sparam_metrics(self) -> tuple[Path | None, dict[str, Any] | None]:
        exports_dir = (PROJECT_ROOT / "artifacts" / "exports").resolve()
        if not exports_dir.exists():
            return None, None

        candidates = sorted(exports_dir.glob("summary_metrics*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for candidate in candidates:
            data = self._load_json_file(candidate)
            if data:
                return candidate, data

        s11_txt = exports_dir / "s11.txt"
        if s11_txt.exists():
            computed = CSTApp.extract_summary_metrics(str(s11_txt))
            if computed:
                return s11_txt, {"s11_metrics": computed}
        return None, None

    def _load_latest_farfield_metrics(self) -> tuple[Path | None, dict[str, Any] | None]:
        exports_dir = (PROJECT_ROOT / "artifacts" / "exports").resolve()
        if not exports_dir.exists():
            return None, None
        candidates = sorted(exports_dir.glob("*_metrics.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for candidate in candidates:
            if candidate.name == "summary_metrics.json":
                continue
            data = self._load_json_file(candidate)
            if data and ("main_lobe_direction_deg" in data or "beamwidth_3db_deg" in data):
                return candidate, data
        return None, None

    @staticmethod
    def _extract_s11_metrics(raw_metrics: dict[str, Any] | None) -> dict[str, float | None]:
        if not raw_metrics:
            return {
                "center_frequency": None,
                "bandwidth_mhz": None,
                "return_loss_db": None,
                "vswr": None,
            }

        s11_data = raw_metrics.get("s11_metrics") if isinstance(raw_metrics, dict) else None
        if not isinstance(s11_data, dict):
            s11_data = raw_metrics

        center = s11_data.get("center_frequency")
        bw_ghz = s11_data.get("bandwidth")
        min_s11_db = s11_data.get("min_s11_db")
        center_val = float(center) if center is not None else None
        bw_mhz_val = float(bw_ghz) * 1000.0 if bw_ghz is not None else None
        rl_val = abs(float(min_s11_db)) if min_s11_db is not None else None

        vswr_val = None
        if rl_val is not None:
            gamma = 10 ** (-rl_val / 20.0)
            if gamma < 1.0:
                vswr_val = (1.0 + gamma) / (1.0 - gamma)
                if vswr_val > 25.0:
                    vswr_val = None

        return {
            "center_frequency": center_val,
            "bandwidth_mhz": bw_mhz_val,
            "return_loss_db": rl_val,
            "vswr": vswr_val,
        }

    def _extract_cst_result_payload(self) -> dict[str, str]:
        _, sparam_metrics = self._load_latest_sparam_metrics()
        _, farfield_metrics = self._load_latest_farfield_metrics()
        s11 = self._extract_s11_metrics(sparam_metrics)

        gain_value = None
        farfield_value = ""
        if farfield_metrics:
            gain_value = farfield_metrics.get("max_realized_gain_dbi") or farfield_metrics.get("max_gain_dbi") or farfield_metrics.get("theta_cut_peak_gain_dbi")
            if farfield_metrics.get("main_lobe_direction_deg") is not None:
                farfield_value = f"{float(farfield_metrics['main_lobe_direction_deg']):.1f}d"
            else:
                farfield_value = "OK"

        result = dict(self.last_result)
        center_frequency = s11.get("center_frequency")
        bandwidth_mhz = s11.get("bandwidth_mhz")
        vswr = s11.get("vswr")
        if center_frequency is not None:
            result["actual_frequency"] = f"{float(center_frequency):.2f}"
        if bandwidth_mhz is not None:
            result["actual_bandwidth"] = f"{float(bandwidth_mhz):.0f}"
        if vswr is not None:
            result["vswr"] = f"{float(vswr):.2f}"
        if gain_value is not None:
            result["gain_db"] = f"{float(gain_value):.2f}"
        if farfield_value:
            result["farfield"] = farfield_value
        return result

    def _build_feedback_payload(self, values: dict[str, Any], completion_requested: bool) -> dict[str, Any]:
        actual_frequency = float(values.get("actual_frequency") or self.last_result.get("actual_frequency") or 0.0)
        actual_bandwidth = float(values.get("actual_bandwidth") or self.last_result.get("actual_bandwidth") or 0.0)
        actual_gain = float(values.get("actual_gain") or self.last_result.get("gain_db") or 0.0)
        actual_vswr = float(values.get("actual_vswr") or self.last_result.get("vswr") or 1.5)

        if actual_frequency <= 0 or actual_bandwidth < 0:
            raise ValueError("Feedback requires valid actual frequency and bandwidth values")

        actual_return_loss_db = values.get("actual_return_loss_db")
        if actual_return_loss_db in (None, ""):
            _, sparam_metrics = self._load_latest_sparam_metrics()
            s11 = self._extract_s11_metrics(sparam_metrics)
            actual_return_loss_db = s11.get("return_loss_db") or 18.0

        sparam_path, _ = self._load_latest_sparam_metrics()
        farfield_path, _ = self._load_latest_farfield_metrics()

        return {
            "schema_version": "client_feedback.v1",
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "design_id": self.design_id,
            "iteration_index": self.iteration_index,
            "simulation_status": "completed",
            "actual_center_frequency_ghz": actual_frequency,
            "actual_bandwidth_mhz": actual_bandwidth,
            "actual_return_loss_db": float(actual_return_loss_db),
            "actual_vswr": actual_vswr,
            "actual_gain_dbi": actual_gain,
            "notes": (
                "User marked this design done from the QML UI."
                if completion_requested
                else "User submitted CST feedback from the QML UI."
            ),
            "artifacts": {
                "s11_trace_ref": str(sparam_path.resolve()) if sparam_path else None,
                "summary_metrics_ref": str(sparam_path.resolve()) if sparam_path else None,
                "farfield_ref": str(farfield_path.resolve()) if farfield_path else None,
                "current_distribution_ref": None,
            },
        }

    @staticmethod
    def _empty_result_payload() -> dict[str, str]:
        return {
            "patch_width": "",
            "patch_length": "",
            "substrate_width": "",
            "substrate_length": "",
            "feed_width": "",
            "feed_length": "",
            "actual_frequency": "",
            "actual_bandwidth": "",
            "farfield": "",
            "gain_db": "",
            "vswr": "",
        }


def main():
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    engine = QQmlApplicationEngine()
    controller = DesignController()
    app.aboutToQuit.connect(controller.shutdown)
    app.lastWindowClosed.connect(app.quit)
    engine.rootContext().setContextProperty("designController", controller)

    qml_path = Path(__file__).parent / "main_modern.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
