"""
ExecutionEngine - Orchestrate command execution

Responsible for:
- Execute commands sequentially
- Track execution state
- Handle errors and failures
- Manage pause/resume
"""

import asyncio
from typing import Dict, List, Any, Optional
from executor.command_parser import CommandPackage, Command
from executor.vba_generator import VBAGenerator
from utils.logger import get_logger


logger = get_logger(__name__)


class ExecutionResult:
    """Result of command execution"""
    
    def __init__(self, command_id: str, success: bool, output: str = "", error: str = ""):
        self.command_id = command_id
        self.success = success
        self.output = output
        self.error = error
        self.timestamp = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "command_id": self.command_id,
            "success": self.success,
            "output": self.output,
            "error": self.error,
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
        logger.info(f"Starting execution of package with {len(package.commands)} commands")
        
        for i, command in enumerate(package.commands):
            if self.paused:
                logger.info("Execution paused")
                # Wait until resumed
                while self.paused:
                    await asyncio.sleep(0.5)
            
            try:
                logger.info(f"Executing command {i+1}/{len(package.commands)}: {command.id} ({command.type})")
                result = await self._execute_command(command)
                self.results.append(result)
                
                if not result.success and command.on_failure == "abort":
                    logger.error(f"Command {command.id} failed, aborting execution")
                    break
            except Exception as e:
                logger.exception(f"Exception executing command {command.id}: {e}")
                result = ExecutionResult(command.id, False, error=str(e))
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
            vba_code = self.vba_generator.generate_macro(command.type, command.parameters)
            
            # TODO: Inject and execute VBA via CST COM interface
            # For now, simulate execution
            await asyncio.sleep(0.1)
            
            result = ExecutionResult(
                command.id,
                success=True,
                output=f"Executed {command.type} successfully"
            )
            logger.debug(f"Command {command.id} execution successful")
            return result
        except Exception as e:
            logger.error(f"Command {command.id} execution failed: {e}")
            return ExecutionResult(
                command.id,
                success=False,
                error=str(e)
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
            "paused": self.paused
        }
    
    def get_results(self) -> List[Dict[str, Any]]:
        """Get all execution results
        
        Returns:
            List of result dictionaries
        """
        return [r.to_dict() for r in self.results]
