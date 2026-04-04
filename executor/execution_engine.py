"""Execute current server command packages in preparation or live mode."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any

from cst.cst_app import CSTApp
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
                result = await self._execute_command(command)
                self.results.append(result)

                if not result.success and command.on_failure == "retry_once":
                    logger.warning(f"Retrying command {command.seq}:{command.command} once")
                    retry_result = await self._execute_command(command)
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
    
    async def _execute_command(self, command: Command) -> ExecutionResult:
        """Execute single command
        
        Args:
            command: Command to execute
            
        Returns:
            ExecutionResult
        """
        try:
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
