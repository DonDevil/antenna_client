"""
ConnectionChecker - Verify server and CST availability

Responsible for:
- Async server health checks
- CST Studio availability detection
- Connection status reporting
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Tuple
from comm.server_connector import ServerConnector
from utils.logger import get_logger


logger = get_logger(__name__)


class ConnectionChecker:
    """Check server and CST availability"""
    
    @staticmethod
    async def check_server() -> Tuple[bool, str, Dict]:
        """Check if server is available and healthy
        
        Returns:
            Tuple of (is_connected, status_message, server_info_dict)
        """
        try:
            config_path = Path(__file__).parent.parent / "config.json"
            with open(config_path, "r") as f:
                config = json.load(f)
            
            server_config = config.get("server", {})
            base_url = server_config.get("base_url", "http://localhost:8000")
            
            async with ServerConnector(base_url, timeout_sec=5) as connector:
                try:
                    result = await connector.get("/api/v1/health")
                    status_msg = f"✅ Connected to {base_url}"
                    return True, status_msg, result
                except Exception as e:
                    status_msg = f"❌ Server Error: {str(e)}"
                    logger.error(f"Server connection failed: {e}")
                    return False, status_msg, {}
        except Exception as e:
            status_msg = f"❌ Configuration Error: {str(e)}"
            logger.error(f"Connection check failed: {e}")
            return False, status_msg, {}
    
    @staticmethod
    def check_cst() -> Tuple[bool, str]:
        """Check if CST Studio is installed
        
        Returns:
            Tuple of (is_available, status_message)
        """
        try:
            config_path = Path(__file__).parent.parent / "config.json"
            with open(config_path, "r") as f:
                config = json.load(f)
            
            cst_config = config.get("cst", {})
            cst_exe = Path(cst_config.get("executable_path", ""))
            
            if cst_exe.exists():
                status_msg = f"✅ CST found at {cst_exe.parent.name}"
                return True, status_msg
            else:
                status_msg = f"❌ CST not found"
                logger.warning(f"CST not found at {cst_exe}")
                return False, status_msg
        except Exception as e:
            status_msg = f"❌ CST check error: {str(e)}"
            logger.error(f"CST check failed: {e}")
            return False, status_msg
    
    @staticmethod
    async def check_all() -> Dict[str, Tuple[bool, str]]:
        """Check all connections
        
        Returns:
            Dict with connection status for each component
        """
        # Check server (async)
        server_ok, server_msg, _ = await ConnectionChecker.check_server()
        
        # Check CST (sync)
        cst_ok, cst_msg = ConnectionChecker.check_cst()
        
        return {
            "server": (server_ok, server_msg),
            "cst": (cst_ok, cst_msg)
        }
