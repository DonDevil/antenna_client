"""
ConnectionChecker - Verify server and CST availability

Responsible for:
- Async server health checks with full health payload
- CST Studio availability detection
- Connection status reporting
- Health status interpretation (available/loading/none)
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Tuple, Any, Optional
from comm.server_connector import ServerConnector
from utils.logger import get_logger


logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConnectionChecker:
    """Check server and CST availability"""
    
    @staticmethod
    async def check_server() -> Tuple[bool, str, Dict[str, Any]]:
        """Check if server is available and healthy
        
        Returns:
            Tuple of (is_connected, status_message, full_health_dict)
        """
        try:
            config_path = PROJECT_ROOT / "config.json"
            with open(config_path, "r") as f:
                config = json.load(f)
            
            server_config = config.get("server", {})
            base_url = server_config.get("base_url", "http://localhost:8000")
            
            async with ServerConnector(base_url, timeout_sec=5) as connector:
                try:
                    result = await connector.get("/api/v1/health")
                    status = result.get("status", "unknown")
                    
                    if status == "ok":
                        ann_status = result.get("ann_status", "unknown")
                        llm_status = result.get("llm_status", "unknown")
                        status_msg = f"✅ Server OK (ANN: {ann_status}, LLM: {llm_status})"
                        return True, status_msg, result
                    else:
                        status_msg = f"⚠️ Server status: {status}"
                        return False, status_msg, result
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
            config_path = PROJECT_ROOT / "config.json"
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
    async def check_all() -> Dict[str, Any]:
        """Check all connections
        
        Returns:
            Dict with connection status and full health payload
        """
        # Check server (async)
        server_ok, server_msg, server_health = await ConnectionChecker.check_server()
        
        # Check CST (sync)
        cst_ok, cst_msg = ConnectionChecker.check_cst()
        
        return {
            "server": (server_ok, server_msg),
            "cst": (cst_ok, cst_msg),
            "health": server_health if server_ok else {}
        }
    
    @staticmethod
    def get_ann_status(health: Dict[str, Any]) -> str:
        """Extract ANN status from health payload
        
        Args:
            health: Health dict from server
            
        Returns:
            ANN status: "available" | "loading" | "none"
        """
        return health.get("ann_status", "none")
    
    @staticmethod
    def get_llm_status(health: Dict[str, Any]) -> str:
        """Extract LLM status from health payload
        
        Args:
            health: Health dict from server
            
        Returns:
            LLM status: "available" | "loading" | "none"
        """
        return health.get("llm_status", "none")

