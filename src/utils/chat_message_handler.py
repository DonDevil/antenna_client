"""UI workflow controller for chat, optimize, execution, feedback, reset, and export."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFileDialog

from comm.api_client import ApiClient
from comm.request_builder import RequestBuilder
from comm.response_handler import ResponseHandler
from comm.server_connector import ServerConnector
from executor.command_parser import CommandParser
from executor.execution_engine import ExecutionEngine
from session.design_exporter import DesignExporter
from utils.logger import get_logger
from utils.validators import extract_antenna_family, extract_frequency_bandwidth


logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _BaseWorker(QThread):
    error_occurred = Signal(str)

    @staticmethod
    def _load_base_url() -> str:
        config_path = PROJECT_ROOT / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("server", {}).get("base_url", "http://localhost:8000")

    @staticmethod
    def _run_async(coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


class ChatRequestWorker(_BaseWorker):
    response_ready = Signal(dict)

    def __init__(self, user_message: str, requirements: dict[str, Any]):
        super().__init__()
        self.user_message = user_message
        self.requirements = requirements

    def run(self):
        try:
            base_url = self._load_base_url()
            result = self._run_async(self._chat_async(base_url))
            self.response_ready.emit(result)
        except Exception as e:
            logger.error(f"Chat worker failed: {type(e).__name__} - {str(e)}")
            self.error_occurred.emit(str(e))

    async def _chat_async(self, base_url: str) -> dict[str, Any]:
        async with ServerConnector(base_url, timeout_sec=30) as connector:
            api = ApiClient(connector)
            try:
                response = await api.chat(self.user_message, self.requirements)
            except Exception:
                response = {}
            try:
                intent_summary = response.get("intent_summary") or await api.parse_intent(self.user_message)
            except Exception:
                intent_summary = {}

        requirements = dict(self.requirements)
        parsed_freq = intent_summary.get("parsed_frequency_ghz")
        parsed_bw = intent_summary.get("parsed_bandwidth_mhz")
        parsed_family = intent_summary.get("parsed_antenna_family")
        if parsed_freq is not None:
            requirements["frequency_ghz"] = float(parsed_freq)
        if parsed_bw is not None:
            requirements["bandwidth_mhz"] = float(parsed_bw)
        if parsed_family:
            requirements["antenna_family"] = parsed_family

        assistant_message = response.get("assistant_message")
        if not assistant_message:
            missing = [
                label
                for label, value in {
                    "frequency_ghz": requirements.get("frequency_ghz"),
                    "bandwidth_mhz": requirements.get("bandwidth_mhz"),
                    "antenna_family": requirements.get("antenna_family"),
                }.items()
                if value in (None, "")
            ]
            if missing:
                assistant_message = f"I still need: {', '.join(missing)}."
            else:
                assistant_message = (
                    "Requirements captured. Review the fields on the right, then press Start Pipeline."
                )

        return {
            "assistant_message": assistant_message,
            "requirements": requirements,
            "intent_summary": intent_summary,
        }


class OptimizeRequestWorker(_BaseWorker):
    response_ready = Signal(dict)

    def __init__(self, user_request: str, design_specs: dict[str, Any], session_id: str | None):
        super().__init__()
        self.user_request = user_request
        self.design_specs = design_specs
        self.session_id = session_id

    def run(self):
        try:
            base_url = self._load_base_url()
            result = self._run_async(self._optimize_async(base_url))
            self.response_ready.emit(result)
        except Exception as e:
            logger.error(f"Optimize worker failed: {type(e).__name__} - {str(e)}")
            self.error_occurred.emit(str(e))

    async def _optimize_async(self, base_url: str) -> dict[str, Any]:
        async with ServerConnector(base_url, timeout_sec=45) as connector:
            api = ApiClient(connector)
            request_builder = RequestBuilder()
            optimize_request = request_builder.build_optimize_request(
                user_text=self.user_request,
                design_specs=self.design_specs,
                session_id=self.session_id,
            )
            logger.info(f"Sending optimize request: {self.user_request}")
            optimize_response = await api.optimize(optimize_request.model_dump())
            return optimize_response.model_dump(mode="json")


class FeedbackRequestWorker(_BaseWorker):
    response_ready = Signal(dict)

    def __init__(self, payload: dict[str, Any]):
        super().__init__()
        self.payload = payload

    def run(self):
        try:
            base_url = self._load_base_url()
            result = self._run_async(self._feedback_async(base_url))
            self.response_ready.emit(result)
        except Exception as e:
            logger.error(f"Feedback worker failed: {type(e).__name__} - {str(e)}")
            self.error_occurred.emit(str(e))

    async def _feedback_async(self, base_url: str) -> dict[str, Any]:
        async with ServerConnector(base_url, timeout_sec=30) as connector:
            api = ApiClient(connector)
            return await api.send_feedback(self.payload)


class CommandExecutionWorker(_BaseWorker):
    response_ready = Signal(dict)

    def __init__(self, command_package: dict[str, Any]):
        super().__init__()
        self.command_package = command_package

    def run(self):
        try:
            result = self._run_async(self._execute_async())
            self.response_ready.emit(result)
        except Exception as e:
            logger.error(f"Execution worker failed: {type(e).__name__} - {str(e)}")
            self.error_occurred.emit(str(e))

    async def _execute_async(self) -> dict[str, Any]:
        parser = CommandParser()
        package = parser.parse_package(self.command_package)
        parser.validate_package(package)

        engine = ExecutionEngine()
        results = await engine.execute_command_package(package)
        return {
            "dry_run": engine.dry_run,
            "results": [result.to_dict() for result in results],
            "progress": engine.get_progress(),
        }


class ChatMessageHandler:
    """Manage the full desktop workflow: chat, optimize, execution, feedback, reset, export."""

    def __init__(self, chat_widget, design_panel, status_bar=None, server_base_url: str = None):
        """Initialize chat message handler

        Args:
            chat_widget: Reference to ChatWidget
            design_panel: Reference to DesignPanel
            status_bar: Optional status bar reference
            server_base_url: Optional server URL override
        """
        self.chat_widget = chat_widget
        self.design_panel = design_panel
        self.status_bar = status_bar
        self.server_base_url = server_base_url
        self.current_worker = None
        self.response_handler = ResponseHandler()
        self.design_exporter = DesignExporter()

        self.requirements = {
            "frequency_ghz": None,
            "bandwidth_mhz": None,
            "antenna_family": None,
        }
        self.current_optimize_response: dict[str, Any] | None = None
        self.current_command_package: dict[str, Any] | None = None
        self.current_execution_results: list[dict[str, Any]] = []
        self.session_id: str | None = None
        self.trace_id: str | None = None
        self.design_id: str | None = None
        self.iteration_index: int = 0

        self.chat_widget.message_submitted.connect(self.handle_user_message)
        self.design_panel.start_pipeline_requested.connect(self.handle_start_pipeline)
        self.design_panel.reset_requested.connect(self.reset_workflow)
        self.design_panel.export_requested.connect(self.export_current_state)
        self.design_panel.feedback_requested.connect(self.handle_feedback_submission)

    def handle_user_message(self, message: str):
        """Send chat text to the server chat/intake path, not optimize."""
        logger.info(f"User message received: {message}")

        if len(message.strip()) < 3:
            self.chat_widget.add_message("Please provide a longer message so I can extract antenna requirements.", "assistant")
            return

        self._show_status("Extracting requirements from chat...")
        self.current_worker = ChatRequestWorker(message, self.requirements.copy())
        self.current_worker.response_ready.connect(self.on_chat_response_received)
        self.current_worker.error_occurred.connect(self.on_error_occurred)
        self.current_worker.start()

    def on_chat_response_received(self, payload: dict[str, Any]):
        """Update the form from chat parsing and show the assistant reply."""
        self.requirements.update(payload.get("requirements", {}))
        self.design_panel.set_spec_values(
            frequency_ghz=self.requirements.get("frequency_ghz"),
            bandwidth_mhz=self.requirements.get("bandwidth_mhz"),
            antenna_family=self.requirements.get("antenna_family"),
        )
        response_text = payload.get("assistant_message", "Requirements updated.")
        logger.info(f"Chat response received: {response_text}")
        self.chat_widget.add_message(response_text, "assistant")
        self._show_status("Requirements updated from chat.")

    def handle_start_pipeline(self):
        """Build optimize request from the form and start the server pipeline."""
        specs = self.design_panel.get_specs()
        validation_error = self._validate_specs(specs)
        if validation_error:
            self.chat_widget.add_message(validation_error, "assistant")
            self._show_status("Cannot start pipeline: invalid specification.")
            return

        user_request = self._build_pipeline_request_text(specs)
        self._show_status("Starting optimization pipeline...")
        self.current_worker = OptimizeRequestWorker(user_request, specs, self.session_id)
        self.current_worker.response_ready.connect(self.on_optimize_response_received)
        self.current_worker.error_occurred.connect(self.on_error_occurred)
        self.current_worker.start()

    def on_optimize_response_received(self, response_data: dict[str, Any]):
        """Persist optimize response, update UI, and kick off command execution."""
        optimize_response = self.response_handler.parse_optimize_response(response_data)
        self.current_optimize_response = response_data
        self.session_id = optimize_response.session_id
        self.trace_id = optimize_response.trace_id
        self.current_command_package = optimize_response.command_package
        self.design_id = None
        self.iteration_index = 0

        command_count = 0
        if optimize_response.command_package:
            command_count = len(optimize_response.command_package.get("commands", []))
            self.design_id = optimize_response.command_package.get("design_id")
            self.iteration_index = int(optimize_response.command_package.get("iteration_index", 0))

        self.design_panel.set_session_metadata(
            optimize_response.session_id,
            optimize_response.trace_id,
            optimize_response.current_stage or "planning_commands",
            command_count,
        )

        response_text = self._format_design_response(optimize_response)
        logger.info(f"Optimize response received: status={optimize_response.status}")
        self.chat_widget.add_message(response_text, "assistant")

        if optimize_response.command_package:
            self._show_status(f"Received {command_count} server commands. Preparing CST execution...")
            self.status_bar.set_progress(0, max(command_count, 1)) if self.status_bar else None
            self.current_worker = CommandExecutionWorker(optimize_response.command_package)
            self.current_worker.response_ready.connect(self.on_execution_completed)
            self.current_worker.error_occurred.connect(self.on_error_occurred)
            self.current_worker.start()
        else:
            self._show_status("Server accepted request without a command package.")

    def on_execution_completed(self, payload: dict[str, Any]):
        """Show execution/preparation results for the current command package."""
        self.current_execution_results = payload.get("results", [])
        progress = payload.get("progress", {})
        dry_run = payload.get("dry_run", True)
        total = progress.get("total", 0)
        completed = progress.get("completed", 0)
        failed = progress.get("failed", 0)

        if self.status_bar:
            self.status_bar.set_progress(total, total)

        mode_text = "prepared for execution" if dry_run else "executed in CST"
        lines = [
            f"Command package {mode_text}.",
            f"Completed: {completed}/{total}",
        ]
        if failed:
            lines.append(f"Failed: {failed}")
            failed_cmds = [item["command_id"] for item in self.current_execution_results if not item.get("success")]
            if failed_cmds:
                lines.append("Failed commands: " + ", ".join(failed_cmds))
        if dry_run:
            lines.append("CST live execution is still running in preparation mode where COM calls are not available.")

        self.chat_widget.add_message("\n".join(lines), "assistant")
        self._show_status("Command package processed.")

    def handle_feedback_submission(self, feedback_values: dict[str, Any]):
        """Submit manual CST feedback to the server for refinement."""
        if not self.session_id or not self.trace_id or not self.design_id:
            self.chat_widget.add_message("Start the pipeline first. Feedback needs an active session.", "assistant")
            return

        if feedback_values["actual_center_frequency_ghz"] <= 0 or feedback_values["actual_bandwidth_mhz"] < 0:
            self.chat_widget.add_message("Feedback requires a valid center frequency and bandwidth.", "assistant")
            return

        sparam_metrics_path, sparam_metrics = self._load_latest_sparam_metrics()
        farfield_metrics_path, farfield_metrics = self._load_latest_farfield_metrics()

        actual_center_frequency_ghz = float(
            sparam_metrics.get("center_frequency", feedback_values["actual_center_frequency_ghz"])
            if sparam_metrics
            else feedback_values["actual_center_frequency_ghz"]
        )
        actual_bandwidth_mhz = float(
            (sparam_metrics.get("bandwidth", 0.0) * 1000.0)
            if sparam_metrics and sparam_metrics.get("bandwidth") is not None
            else feedback_values["actual_bandwidth_mhz"]
        )
        actual_return_loss_db = float(
            sparam_metrics.get("min_s11_db", -18.0)
            if sparam_metrics
            else -18.0
        )

        parsed_gain = None
        if farfield_metrics:
            parsed_gain = farfield_metrics.get("max_realized_gain_dbi")
            if parsed_gain is None:
                parsed_gain = farfield_metrics.get("max_gain_dbi")
            if parsed_gain is None:
                parsed_gain = farfield_metrics.get("theta_cut_peak_gain_dbi")
        actual_gain_dbi = float(parsed_gain if parsed_gain is not None else feedback_values["actual_gain_dbi"])

        payload = {
            "schema_version": "client_feedback.v1",
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "design_id": self.design_id,
            "iteration_index": self.iteration_index,
            "simulation_status": "completed",
            "actual_center_frequency_ghz": actual_center_frequency_ghz,
            "actual_bandwidth_mhz": actual_bandwidth_mhz,
            "actual_return_loss_db": actual_return_loss_db,
            "actual_vswr": feedback_values["actual_vswr"],
            "actual_gain_dbi": actual_gain_dbi,
            "notes": f"Iteration {self.iteration_index}: CST simulation completed successfully.",
            "artifacts": {
                "s11_trace_ref": f"artifacts/s11_iter{self.iteration_index}.json",
                "summary_metrics_ref": (
                    self._to_workspace_relative_path(sparam_metrics_path)
                    if sparam_metrics_path
                    else f"artifacts/summary_iter{self.iteration_index}.json"
                ),
                "farfield_ref": self._to_workspace_relative_path(farfield_metrics_path) if farfield_metrics_path else None,
                "current_distribution_ref": None,
            },
        }

        self._show_status("Submitting CST feedback to server...")
        self.current_worker = FeedbackRequestWorker(payload)
        self.current_worker.response_ready.connect(self.on_feedback_response_received)
        self.current_worker.error_occurred.connect(self.on_error_occurred)
        self.current_worker.start()

    def on_feedback_response_received(self, response_data: dict[str, Any]):
        """Handle server feedback response and optional refinement package."""
        status = response_data.get("status", "unknown")
        self.chat_widget.add_message(f"Feedback accepted. Server status: {status}.", "assistant")

        next_package = response_data.get("next_command_package")
        if next_package:
            self.current_command_package = next_package
            self.iteration_index = int(next_package.get("iteration_index", self.iteration_index + 1))
            self.design_id = next_package.get("design_id", self.design_id)
            self.design_panel.set_session_metadata(
                self.session_id,
                self.trace_id,
                "refinement_commands",
                len(next_package.get("commands", [])),
            )
            self.chat_widget.add_message("Server returned refinement commands. Preparing the next iteration.", "assistant")
            self.current_worker = CommandExecutionWorker(next_package)
            self.current_worker.response_ready.connect(self.on_execution_completed)
            self.current_worker.error_occurred.connect(self.on_error_occurred)
            self.current_worker.start()
        else:
            self._show_status("Feedback processed.")

    def on_error_occurred(self, error: str):
        """Handle workflow errors from any worker."""
        logger.error(f"Workflow error: {error}")
        error_msg = self._normalize_error_message(error)
        self.chat_widget.add_message(error_msg, "assistant")
        self._show_status("Operation failed.")

    def reset_workflow(self):
        """Reset chat, extracted requirements, pipeline state, and panel values."""
        self.chat_widget.clear_history()
        self.design_panel.reset_values()
        self.requirements = {
            "frequency_ghz": None,
            "bandwidth_mhz": None,
            "antenna_family": None,
        }
        self.current_optimize_response = None
        self.current_command_package = None
        self.current_execution_results = []
        self.session_id = None
        self.trace_id = None
        self.design_id = None
        self.iteration_index = 0
        self.chat_widget.add_message("Tell me your antenna requirement. I will update the fields, then you can start the pipeline.", "assistant")
        self._show_status("Workflow reset.")

    def export_current_state(self):
        """Export the current desktop workflow state to a JSON file."""
        if not self.current_optimize_response and not self.chat_widget.get_messages():
            self.chat_widget.add_message("Nothing to export yet. Chat first or start a pipeline.", "assistant")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self.chat_widget,
            "Export Current Design State",
            str(Path("exports") / "antenna_client_session.json"),
            "JSON Files (*.json)",
        )
        if not filepath:
            return

        export_payload = {
            "requirements": self.requirements,
            "design_specs": self.design_panel.get_specs(),
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "design_id": self.design_id,
            "iteration_index": self.iteration_index,
            "optimize_response": self.current_optimize_response,
            "command_package": self.current_command_package,
            "execution_results": self.current_execution_results,
            "chat_history": self.chat_widget.get_messages(),
        }
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        if self.design_exporter.export_to_json(export_payload, filepath):
            self.chat_widget.add_message(f"Exported current workflow state to {filepath}", "assistant")
            self._show_status("Export complete.")
        else:
            self.chat_widget.add_message("Export failed. Check the log for details.", "assistant")

    def _build_pipeline_request_text(self, specs: dict[str, Any]) -> str:
        """Build a stable user_request for optimize using chat history plus form values."""
        last_user_message = ""
        for msg in reversed(self.chat_widget.get_messages()):
            if msg.get("sender") == "user":
                last_user_message = msg.get("text", "")
                break

        family = specs["antenna_family"]
        frequency = specs["frequency_ghz"]
        bandwidth = specs["bandwidth_mhz"]
        if last_user_message:
            return (
                f"{last_user_message}\n\n"
                f"Confirmed desktop fields: family={family}, frequency_ghz={frequency}, bandwidth_mhz={bandwidth}."
            )
        return f"Design a {family} antenna at {frequency} GHz with {bandwidth} MHz bandwidth."

    def _validate_specs(self, specs: dict[str, Any]) -> str | None:
        frequency = float(specs.get("frequency_ghz", 0.0))
        bandwidth = float(specs.get("bandwidth_mhz", 0.0))
        family = specs.get("antenna_family")
        if not 0.1 <= frequency <= 100.0:
            return "Frequency must be between 0.1 and 100 GHz before starting the pipeline."
        if not 1.0 <= bandwidth <= 5000.0:
            return "Bandwidth must be between 1 and 5000 MHz before starting the pipeline."
        if family not in {"amc_patch", "microstrip_patch", "wban_patch"}:
            return "Antenna family must be one of: amc_patch, microstrip_patch, wban_patch."
        return None

    def _normalize_error_message(self, error: str) -> str:
        if "422" in error:
            return "Server rejected the request. Check the entered family, frequency, bandwidth, and constraint values."
        if "Connection" in error or "refused" in error:
            return "Cannot connect to the antenna server. Verify the Ubuntu server URL and that the API is running."
        if "ReadTimeout" in error:
            return "The server took too long to respond. Try again or simplify the request before starting the pipeline."
        return f"Operation failed: {error}"

    def _show_status(self, message: str):
        if self.status_bar is not None:
            self.status_bar.show_message(message, 5000)

    @staticmethod
    def _to_workspace_relative_path(path: Path | None) -> str | None:
        if path is None:
            return None
        try:
            return str(path.resolve().relative_to(Path.cwd().resolve())).replace("\\", "/")
        except Exception:
            return str(path).replace("\\", "/")

    @staticmethod
    def _load_json_file(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            return None
        return None

    def _load_latest_sparam_metrics(self) -> tuple[Path | None, dict[str, Any] | None]:
        metrics_path = (Path("artifacts") / "exports" / "summary_metrics.json").resolve()
        return metrics_path, self._load_json_file(metrics_path)

    def _load_latest_farfield_metrics(self) -> tuple[Path | None, dict[str, Any] | None]:
        exports_dir = (Path("artifacts") / "exports").resolve()
        if not exports_dir.exists():
            return None, None

        candidates = sorted(
            exports_dir.glob("*_metrics.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for candidate in candidates:
            if candidate.name == "summary_metrics.json":
                continue
            data = self._load_json_file(candidate)
            if not data:
                continue
            if "main_lobe_direction_deg" in data or "beamwidth_3db_deg" in data:
                return candidate, data
        return None, None

    @staticmethod
    def _format_design_response(resp) -> str:
        """Format a human-readable summary from an accepted/completed OptimizeResponse."""
        lines = []

        if resp.ann_prediction:
            pred = resp.ann_prediction
            dims = pred.dimensions
            confidence_pct = int(pred.confidence * 100)
            lines.append(f"Antenna design ready (ANN confidence: {confidence_pct}%).")
            lines.append("")
            lines.append("Predicted Dimensions:")
            lines.append(f"  Patch:      {dims.patch_length_mm:.2f} × {dims.patch_width_mm:.2f} mm  (h={dims.patch_height_mm:.4f} mm)")
            lines.append(f"  Substrate:  {dims.substrate_length_mm:.2f} × {dims.substrate_width_mm:.2f} mm  (h={dims.substrate_height_mm:.3f} mm)")
            lines.append(f"  Feed line:  {dims.feed_length_mm:.2f} mm long × {dims.feed_width_mm:.3f} mm wide")
            lines.append(f"  Feed offset: ({dims.feed_offset_x_mm:.4f}, {dims.feed_offset_y_mm:.4f}) mm")
        else:
            lines.append("Design accepted by server.")

        if resp.command_package:
            cmds = resp.command_package.get("commands", [])
            lines.append("")
            lines.append(f"Command package ready with {len(cmds)} commands:")
            for cmd in cmds:
                lines.append(f"  [{cmd['seq']:2d}] {cmd['command']} -> {json.dumps(cmd['params'])}")

        if resp.warnings:
            lines.append("")
            lines.append("Surrogate validation notes:")
            for w in resp.warnings:
                lines.append(f"  - {w}")

        if resp.session_id:
            lines.append("")
            lines.append(f"Session ID: {resp.session_id}")

        return "\n".join(lines)
