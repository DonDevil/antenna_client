"""
CheckpointManager - Save and restore execution checkpoints

Responsible for:
- Save checkpoint before execution
- Restore from checkpoint on error
- Cleanup old checkpoints
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from utils.logger import get_logger


logger = get_logger(__name__)


class CheckpointManager:
    """Manage execution checkpoints for recovery"""
    
    def __init__(self, checkpoint_dir: str = "checkpoints"):
        """Initialize checkpoint manager
        
        Args:
            checkpoint_dir: Directory for checkpoint files
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
        logger.info(f"CheckpointManager initialized with dir: {self.checkpoint_dir}")
    
    def save_checkpoint(self, session_id: str, state: Dict[str, Any]) -> str:
        """Save execution checkpoint
        
        Args:
            session_id: Session ID
            state: State to save
            
        Returns:
            Checkpoint file path
        """
        try:
            checkpoint_file = self.checkpoint_dir / f"{session_id}_checkpoint.json"
            
            state["checkpoint_time"] = datetime.now().isoformat()
            
            with open(checkpoint_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            logger.info(f"Saved checkpoint: {checkpoint_file}")
            return str(checkpoint_file)
        except Exception as e:
            logger.error(f"Checkpoint save failed: {e}")
            return ""
    
    def load_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load execution checkpoint
        
        Args:
            session_id: Session ID
            
        Returns:
            State dict or None if not found
        """
        try:
            checkpoint_file = self.checkpoint_dir / f"{session_id}_checkpoint.json"
            
            if not checkpoint_file.exists():
                logger.warning(f"Checkpoint not found: {checkpoint_file}")
                return None
            
            with open(checkpoint_file, 'r') as f:
                state = json.load(f)
            
            logger.info(f"Loaded checkpoint: {checkpoint_file}")
            return state
        except Exception as e:
            logger.error(f"Checkpoint load failed: {e}")
            return None
    
    def cleanup_checkpoints(self, max_age_hours: int = 24) -> None:
        """Cleanup old checkpoints
        
        Args:
            max_age_hours: Maximum age in hours
        """
        try:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(hours=max_age_hours)
            
            for checkpoint_file in self.checkpoint_dir.glob("*.json"):
                mtime = datetime.fromtimestamp(checkpoint_file.stat().st_mtime)
                if mtime < cutoff:
                    checkpoint_file.unlink()
                    logger.info(f"Deleted old checkpoint: {checkpoint_file}")
        except Exception as e:
            logger.error(f"Checkpoint cleanup failed: {e}")
