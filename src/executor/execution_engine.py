"""Execute current server command packages in preparation or live mode."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Dict, List, Any

from cst_client.cst_app import CSTApp
from executor.command_parser import CommandPackage, Command
from executor.vba_generator import VBAGenerator
from utils.logger import get_logger


logger = get_logger(__name__)


class ExecutionResult:
    """Result of command execution"""
    
    def __init__(self, command_id: str, success: bool, output: str = "", error: str = "", macro: str = ""):
        self.command_id = command_id
        self.success = success
        self.output = output
        self.error = error
        self.macro = macro
        self.timestamp = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "command_id": self.command_id,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "macro": self.macro,
            "timestamp": self.timestamp
        }


class ExecutionEngine:
    """Orchestrate execution of command packages"""
    
    def __init__(self):
        """Initialize execution engine"""
        self.vba_generator = VBAGenerator()
        self.current_execution = None
        self.paused = False
        self.results: List[ExecutionResult] = []
        self.cst_app = CSTApp()
        self.dry_run = True
        self.artifacts: Dict[str, Any] = {}
        self._scoped_hint_cache: Dict[str, str] = {}
        logger.info("ExecutionEngine initialized")
    
    async def execute_command_package(self, package: CommandPackage) -> List[ExecutionResult]:
        """Execute all commands in package
        
        Args:
            package: CommandPackage to execute
            
        Returns:
            List of ExecutionResult objects
            
        Raises:
            RuntimeError: If execution fails
        """
        self.results = []
        self.artifacts = {
            "session_id": package.session_id,
            "trace_id": package.trace_id,
            "design_id": package.design_id,
            "iteration_index": int(package.iteration_index),
        }
        self._scoped_hint_cache = {}
        self.dry_run = not self.cst_app.connect()
        logger.info(f"Starting execution of package with {len(package.commands)} commands")
        
        for i, command in enumerate(package.commands):
            if self.paused:
                logger.info("Execution paused")
                # Wait until resumed
                while self.paused:
                    await asyncio.sleep(0.5)
            
            try:
                logger.info(
                    f"Executing command {i+1}/{len(package.commands)}: "
                    f"{command.seq}:{command.command}"
                )
                result = await self._execute_command(command, package)
                self.results.append(result)

                if not result.success and command.on_failure == "retry_once":
                    logger.warning(f"Retrying command {command.seq}:{command.command} once")
                    retry_result = await self._execute_command(command, package)
                    self.results.append(retry_result)
                    result = retry_result

                if not result.success and command.on_failure == "abort":
                    logger.error(f"Command {command.seq}:{command.command} failed, aborting execution")
                    break
            except Exception as e:
                logger.exception(f"Exception executing command {command.seq}:{command.command}: {e}")
                result = ExecutionResult(f"{command.seq}:{command.command}", False, error=str(e))
                self.results.append(result)
                break
        
        logger.info(f"Execution complete. {sum(1 for r in self.results if r.success)}/{len(self.results)} succeeded")
        return self.results
    
    @staticmethod
    def _sanitize_token(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return "unknown"
        return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_") or "unknown"

    def _scoped_destination_hint(self, package: CommandPackage, base_hint: str) -> str:
        base = self._sanitize_token(base_hint or "artifact")
        cached = self._scoped_hint_cache.get(base)
        if cached:
            return cached

        session_part = self._sanitize_token(package.session_id)[:16]
        design_part = self._sanitize_token(package.design_id)[:20]
        scoped = f"{session_part}_iter{int(package.iteration_index)}_{design_part}_{base}"
        self._scoped_hint_cache[base] = scoped
        return scoped

    def _record_artifact(self, key: str, path_value: Any) -> None:
        if not path_value:
            return
        try:
            self.artifacts[key] = str(Path(path_value).resolve())
        except Exception:
            self.artifacts[key] = str(path_value)

    async def _execute_command(self, command: Command, package: CommandPackage) -> ExecutionResult:
        """Execute single command
        
        Args:
            command: Command to execute
            
        Returns:
            ExecutionResult
        """
        try:
            if command.command == "create_project":
                project_name = str(command.params.get("project_name", "server_generated_project"))
                project_path = self.cst_app.create_project(project_name) if not self.dry_run else None
                if not self.dry_run and not project_path:
                    return ExecutionResult(
                        f"{command.seq}:{command.command}",
                        success=False,
                        error=f"Failed to create CST project: {project_name}",
                    )
                mode = "prepared" if self.dry_run else "executed"
                return ExecutionResult(
                    f"{command.seq}:{command.command}",
                    success=True,
                    output=f"{mode.capitalize()} create_project successfully",
                    macro="",
                )

            if command.command == "run_simulation":
                timeout_sec = int(command.params.get("timeout_sec", 600))
                if not self.dry_run and not self.cst_app.run_simulation(timeout_sec=timeout_sec):
                    return ExecutionResult(
                        f"{command.seq}:{command.command}",
                        success=False,
                        error=f"Failed to run simulation with timeout_sec={timeout_sec}",
                    )
                mode = "prepared" if self.dry_run else "executed"
                return ExecutionResult(
                    f"{command.seq}:{command.command}",
                    success=True,
                    output=f"{mode.capitalize()} run_simulation successfully",
                    macro="",
                )

            if command.command == "export_s_parameters":
                base_hint = str(command.params.get("destination_hint", "s11"))
                destination_hint = self._scoped_destination_hint(package, base_hint)
                if not self.dry_run:
                    exported_path = self.cst_app.export_s_parameters(destination_hint=destination_hint)
                    if not exported_path:
                        return ExecutionResult(
                            f"{command.seq}:{command.command}",
                            success=False,
                            error="Failed to export S-parameters from CST",
                        )
                    self._record_artifact("s11_trace_path", exported_path)
                    self.artifacts["s11_destination_hint"] = destination_hint
                    output = f"Exported S-parameters to {exported_path}"
                else:
                    output = "Prepared export_s_parameters in dry-run mode"
                return ExecutionResult(
                    f"{command.seq}:{command.command}",
                    success=True,
                    output=output,
                    macro="",
                )

            if command.command == "extract_summary_metrics":
                if not self.dry_run:
                    base_hint = str(command.params.get("destination_hint", "s11"))
                    destination_hint = self._scoped_destination_hint(package, base_hint)
                    sparam_path = self.cst_app.export_s_parameters(destination_hint=destination_hint)
                    if not sparam_path:
                        return ExecutionResult(
                            f"{command.seq}:{command.command}",
                            success=False,
                            error="Failed to export S-parameters before metric extraction",
                        )
                    metrics = self.cst_app.extract_summary_metrics(sparam_path)
                    if not metrics:
                        return ExecutionResult(
                            f"{command.seq}:{command.command}",
                            success=False,
                            error="Failed to parse summary metrics from S-parameter export",
                        )
                    summary_metrics_path = (Path("artifacts") / "exports" / f"{destination_hint}_summary_metrics.json").resolve()
                    summary_payload = {
                        "s11_metrics": metrics,
                        "farfield_metrics": None,
                        "session_id": package.session_id,
                        "trace_id": package.trace_id,
                        "design_id": package.design_id,
                        "iteration_index": int(package.iteration_index),
                        "destination_hint": destination_hint,
                    }
                    summary_metrics_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
                    self._record_artifact("s11_trace_path", sparam_path)
                    self._record_artifact("summary_metrics_path", summary_metrics_path)
                    self.artifacts["s11_destination_hint"] = destination_hint
                    output = f"Extracted metrics: {json.dumps(metrics)}"
                else:
                    output = "Prepared extract_summary_metrics in dry-run mode"
                return ExecutionResult(
                    f"{command.seq}:{command.command}",
                    success=True,
                    output=output,
                    macro="",
                )

            if command.command == "export_farfield":
                base_hint = str(command.params.get("destination_hint", "farfield"))
                destination_hint = self._scoped_destination_hint(package, base_hint)
                frequency_ghz = float(command.params.get("frequency_ghz", 2.4))
                if not self.dry_run:
                    exported_path = self.cst_app.export_farfield(
                        frequency_ghz=frequency_ghz,
                        destination_hint=destination_hint,
                    )
                    if not exported_path:
                        return ExecutionResult(
                            f"{command.seq}:{command.command}",
                            success=False,
                            error="Failed to export far-field data from CST",
                        )
                    farfield_metrics_path = (Path("artifacts") / "exports" / f"{destination_hint}_metrics.json").resolve()
                    farfield_summary_path = (Path("artifacts") / "exports" / f"{destination_hint}_summary.txt").resolve()
                    farfield_theta_cut_path = (Path("artifacts") / "exports" / f"{destination_hint}_theta_cut.txt").resolve()
                    farfield_metadata_path = (Path("artifacts") / "exports" / f"{destination_hint}_meta.json").resolve()
                    metrics = self.cst_app.extract_farfield_metrics(destination_hint=destination_hint)
                    self._record_artifact("farfield_source_path", exported_path)
                    self._record_artifact("farfield_metrics_path", farfield_metrics_path)
                    self._record_artifact("farfield_summary_path", farfield_summary_path)
                    self._record_artifact("farfield_theta_cut_path", farfield_theta_cut_path)
                    self._record_artifact("farfield_metadata_path", farfield_metadata_path)
                    self.artifacts["farfield_destination_hint"] = destination_hint
                    if metrics:
                        output = (
                            f"Exported far-field data to {exported_path}; "
                            f"main_lobe={metrics.get('main_lobe_direction_deg')} deg, "
                            f"beamwidth_3db={metrics.get('beamwidth_3db_deg')} deg, "
                            f"max_realized_gain={metrics.get('max_realized_gain_dbi')} dBi"
                        )
                    else:
                        output = f"Exported far-field data to {exported_path}"
                else:
                    output = "Prepared export_farfield in dry-run mode"
                return ExecutionResult(
                    f"{command.seq}:{command.command}",
                    success=True,
                    output=output,
                    macro="",
                )

            if command.command == "extract_farfield_metrics":
                base_hint = str(command.params.get("destination_hint", "farfield"))
                destination_hint = self._scoped_destination_hint(package, base_hint)
                if not self.dry_run:
                    metrics = self.cst_app.extract_farfield_metrics(destination_hint=destination_hint)
                    if not metrics:
                        return ExecutionResult(
                            f"{command.seq}:{command.command}",
                            success=False,
                            error=(
                                "Failed to extract far-field metrics. "
                                "Run export_farfield first for the same destination_hint."
                            ),
                        )
                    self._record_artifact("farfield_metrics_path", Path("artifacts") / "exports" / f"{destination_hint}_metrics.json")
                    self.artifacts["farfield_destination_hint"] = destination_hint
                    output = f"Extracted far-field metrics: {json.dumps(metrics)}"
                else:
                    output = "Prepared extract_farfield_metrics in dry-run mode"
                return ExecutionResult(
                    f"{command.seq}:{command.command}",
                    success=True,
                    output=output,
                    macro="",
                )

            # Generate VBA for command
            vba_code = self.vba_generator.generate_macro(command.command, command.params)

            artifacts_dir = Path("artifacts") / "vba"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            macro_path = artifacts_dir / f"{command.seq:02d}_{command.command}.bas"
            macro_path.write_text(vba_code, encoding="utf-8")

            # Best-effort execution path. Existing CST COM integration remains partial,
            # so the engine transparently falls back to dry-run preparation mode.
            if not self.dry_run:
                executed = self.cst_app.execute_macro(vba_code)
                if not executed:
                    logger.warning(
                        f"CST COM execution unavailable for {command.seq}:{command.command}; "
                        "continuing in dry-run preparation mode"
                    )
                    self.dry_run = True

            await asyncio.sleep(0.1)
            mode = "prepared" if self.dry_run else "executed"
            result = ExecutionResult(
                f"{command.seq}:{command.command}",
                success=True,
                output=f"{mode.capitalize()} {command.command} successfully",
                macro=vba_code,
            )
            logger.debug(f"Command {command.seq}:{command.command} execution successful")
            return result
        except Exception as e:
            logger.error(f"Command {command.seq}:{command.command} execution failed: {e}")
            return ExecutionResult(
                f"{command.seq}:{command.command}",
                success=False,
                error=str(e),
                macro=vba_code if 'vba_code' in locals() else "",
            )
    
    def pause_execution(self) -> None:
        """Pause execution"""
        self.paused = True
        logger.info("Execution paused")
    
    def resume_execution(self) -> None:
        """Resume execution"""
        self.paused = False
        logger.info("Execution resumed")
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current execution progress
        
        Returns:
            Dictionary with progress info
        """
        total = len(self.results)
        completed = sum(1 for r in self.results if r.success)
        
        return {
            "total": total,
            "completed": completed,
            "failed": sum(1 for r in self.results if not r.success),
            "in_progress": False,
            "paused": self.paused,
            "dry_run": self.dry_run,
        }
    
    def get_results(self) -> List[Dict[str, Any]]:
        """Get all execution results
        
        Returns:
            List of result dictionaries
        """
        return [r.to_dict() for r in self.results]

    def get_artifacts(self) -> Dict[str, Any]:
        """Get exact artifact paths produced for the current package execution."""
        return dict(self.artifacts)
