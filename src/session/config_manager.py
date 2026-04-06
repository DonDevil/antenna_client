"""
ConfigManager - Configuration file management

Responsible for:
- Load configuration from config.json
- User preferences
- Default values
- Configuration validation
"""

import json
from typing import Dict, Any, Optional
from pathlib import Path
from utils.logger import get_logger


logger = get_logger(__name__)


class ConfigManager:
    """Manage application configuration"""
    
    def __init__(self, config_file: str = "config.json"):
        """Initialize config manager
        
        Args:
            config_file: Path to config.json
        """
        self.config_file = Path(config_file)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file
        
        Returns:
            Configuration dictionary
        """
        if not self.config_file.exists():
            logger.warning(f"Config file not found: {self.config_file}")
            return self._default_config()
        
        try:
            with open(self.config_file) as f:
                config = json.load(f)
            logger.info(f"Loaded config from {self.config_file}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default configuration
        
        Returns:
            Default config dictionary
        """
        return {
            "server": {
                "base_url": "http://localhost:8000",
                "timeout_sec": 60,
                "retry_count": 3
            },
            "ui": {
                "theme": "light",
                "default_width": 1400,
                "default_height": 900
            }
        }
    
    def get(self, key: str, default=None) -> Any:
        """Get configuration value
        
        Args:
            key: Configuration key (dot notation, e.g., "server.base_url")
            default: Default value if not found
            
        Returns:
            Configuration value
        """
        parts = key.split('.')
        value = self.config
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return default
        
        return value if value is not None else default
    
    def save(self) -> bool:
        """Save configuration to file
        
        Returns:
            True if saved successfully
        """
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Saved config to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
