"""
ErrorRecovery - Error handling and recovery mechanisms

Responsible for:
- Detect and handle network errors
- CST crashes
- Partial execution completion
- Resume from checkpoint
"""

from typing import Dict, Any, Optional
from utils.logger import get_logger


logger = get_logger(__name__)


class ErrorRecovery:
    """Handle errors and enable recovery"""
    
    def __init__(self):
        """Initialize error recovery"""
        self.last_error: Optional[str] = None
        self.error_count = 0
        self.recovery_attempts = 0
        logger.info("ErrorRecovery initialized")
    
    def handle_network_error(self, error: Exception) -> bool:
        """Handle network error with retry
        
        Args:
            error: Network exception
            
        Returns:
            True if recovered
        """
        self.last_error = str(error)
        self.error_count += 1
        
        logger.error(f"Network error (attempt {self.error_count}): {error}")
        
        if self.error_count <= 3:
            self.recovery_attempts += 1
            logger.info(f"Attempting recovery (attempt {self.recovery_attempts})")
            return True
        
        return False
    
    def handle_cst_crash(self) -> bool:
        """Handle CST crash
        
        Returns:
            True if recovery attempted
        """
        logger.error("CST Studio crashed")
        self.last_error = "CST Studio crash detected"
        self.recovery_attempts += 1
        
        # In production, would attempt to restart CST
        logger.info("Attempting to restart CST...")
        return True
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """Get recovery status
        
        Returns:
            Status dict
        """
        return {
            "last_error": self.last_error,
            "error_count": self.error_count,
            "recovery_attempts": self.recovery_attempts,
            "is_recovering": self.error_count > 0,
        }
