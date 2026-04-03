"""
ProgressTracker - Track execution progress and status

Responsible for:
- Track overall progress percentage
- Per-command status
- Estimated time remaining
- Pause/resume capability
"""

from typing import Dict, Any
from datetime import datetime, timedelta
from utils.logger import get_logger


logger = get_logger(__name__)


class ProgressTracker:
    """Track execution progress"""
    
    def __init__(self, total_commands: int):
        """Initialize progress tracker
        
        Args:
            total_commands: Total number of commands to execute
        """
        self.total_commands = total_commands
        self.completed_commands = 0
        self.failed_commands = 0
        self.start_time = None
        self.command_times = []
        self.status = "idle"  # idle, running, paused, completed
        logger.info(f"ProgressTracker initialized with {total_commands} commands")
    
    def start(self) -> None:
        """Start tracking"""
        self.start_time = datetime.now()
        self.status = "running"
        logger.debug("Progress tracking started")
    
    def end(self) -> None:
        """End tracking"""
        self.status = "completed"
        logger.debug("Progress tracking ended")
    
    def command_started(self) -> None:
        """Mark command as started"""
        self.status = "running"
    
    def command_completed(self, success: bool = True) -> None:
        """Mark command as completed
        
        Args:
            success: Whether command succeeded
        """
        if success:
            self.completed_commands += 1
        else:
            self.failed_commands += 1
        
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            self.command_times.append(elapsed)
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress
        
        Returns:
            Dictionary with progress info
        """
        percent = 0
        if self.total_commands > 0:
            percent = int((self.completed_commands / self.total_commands) * 100)
        
        return {
            "total": self.total_commands,
            "completed": self.completed_commands,
            "failed": self.failed_commands,
            "percentage": percent,
            "status": self.status
        }
    
    def get_eta(self) -> Dict[str, Any]:
        """Get estimated time to completion
        
        Returns:
            Dictionary with time estimates
        """
        if not self.command_times or self.start_time is None:
            return {
                "estimated_remaining_sec": None,
                "estimated_completion_time": None,
                "average_command_time_sec": None
            }
        
        avg_time = sum(self.command_times) / len(self.command_times)
        remaining_commands = self.total_commands - self.completed_commands
        estimated_remaining = avg_time * remaining_commands
        
        eta_time = datetime.now() + timedelta(seconds=estimated_remaining)
        
        return {
            "estimated_remaining_sec": estimated_remaining,
            "estimated_completion_time": eta_time.isoformat(),
            "average_command_time_sec": avg_time
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary
        
        Returns:
            Dictionary with summary info
        """
        elapsed = None
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
        
        return {
            **self.get_progress(),
            **self.get_eta(),
            "elapsed_sec": elapsed,
            "success_rate": (self.completed_commands / self.total_commands * 100) if self.total_commands > 0 else 0
        }
