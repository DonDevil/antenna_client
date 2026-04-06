"""Initialization flow for client startup according to server handoff."""

from __future__ import annotations

import asyncio
from typing import Dict, Any, Optional, Callable

from comm.api_client import ApiClient
from comm.server_connector import ServerConnector
from utils.logger import get_logger


logger = get_logger(__name__)


class InitializationState:
    """Tracks initialization progress."""
    
    def __init__(self):
        self.health_ok = False
        self.health_payload: Dict[str, Any] = {}
        self.capabilities_ok = False
        self.capabilities: Dict[str, Any] = {}
        self.ann_status = "none"
        self.llm_status = "none"
        self.errors: list[str] = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return {
            "health_ok": self.health_ok,
            "health_payload": self.health_payload,
            "capabilities_ok": self.capabilities_ok,
            "capabilities": self.capabilities,
            "ann_status": self.ann_status,
            "llm_status": self.llm_status,
            "errors": self.errors,
        }


class ClientInitializer:
    """Manages client initialization flow per server handoff.
    
    Recommended sequence:
    1. GET /api/v1/health
    2. Poll until warm-up completes (if loading)
    3. GET /api/v1/capabilities
    4. Show UI with capabilities
    """
    
    def __init__(self, connector: ServerConnector):
        """Initialize client initializer
        
        Args:
            connector: ServerConnector instance
        """
        self.connector = connector
        self.api_client = ApiClient(connector)
        self.state = InitializationState()
        self.progress_callbacks: list[Callable] = []
    
    def on_progress(self, callback: Callable) -> None:
        """Register progress callback
        
        Args:
            callback: Async callable(progress_message, state) to call on progress
        """
        self.progress_callbacks.append(callback)
    
    async def _notify_progress(self, message: str) -> None:
        """Notify progress listeners
        
        Args:
            message: Progress message
        """
        logger.info(f"Init: {message}")
        for callback in self.progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message, self.state)
                else:
                    callback(message, self.state)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
    
    async def initialize(self, max_warm_up_polls: int = 10) -> bool:
        """Run full initialization sequence
        
        Args:
            max_warm_up_polls: Max times to poll during warm-up
            
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Step 1: Check health
            await self._notify_progress("Checking server health...")
            if not await self._check_health():
                return False
            
            # Step 2: Poll for warm-up if needed
            if self.state.llm_status == "loading" or self.state.ann_status == "loading":
                await self._notify_progress("Waiting for server warm-up...")
                if not await self._poll_warm_up(max_warm_up_polls):
                    await self._notify_progress(
                        f"⚠️ Warm-up incomplete. LLM: {self.state.llm_status}, ANN: {self.state.ann_status}"
                    )
                    # Continue anyway - fallback behavior
            
            # Step 3: Load capabilities
            await self._notify_progress("Loading server capabilities...")
            if not await self._load_capabilities():
                return False
            
            await self._notify_progress("✅ Initialization complete!")
            return True
            
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            self.state.errors.append(str(e))
            await self._notify_progress(f"❌ Initialization error: {e}")
            return False
    
    async def _check_health(self) -> bool:
        """Check server health
        
        Returns:
            True if health check successful
        """
        try:
            health = await self.api_client.health_check()
            status = health.get("status", "unknown")
            
            if status != "ok":
                self.state.errors.append(f"Server status: {status}")
                await self._notify_progress(f"❌ Server status is {status}")
                return False
            
            self.state.health_ok = True
            self.state.health_payload = health
            self.state.ann_status = health.get("ann_status", "none")
            self.state.llm_status = health.get("llm_status", "none")
            
            ann_msg = health.get("ann_message", "")
            llm_msg = health.get("llm_message", "")
            
            await self._notify_progress(
                f"✅ Server ready - ANN: {self.state.ann_status}, LLM: {self.state.llm_status}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.state.errors.append(f"Health check failed: {e}")
            await self._notify_progress(f"❌ Health check failed: {e}")
            return False
    
    async def _poll_warm_up(self, max_polls: int = 10) -> bool:
        """Poll until models are ready
        
        Args:
            max_polls: Maximum number of polls
            
        Returns:
            True if both models become available, False if timeout
        """
        for poll_num in range(max_polls):
            try:
                health = await self.api_client.health_check()
                self.state.ann_status = health.get("ann_status", "none")
                self.state.llm_status = health.get("llm_status", "none")
                
                # Check if both are ready
                if self.state.ann_status == "available" and self.state.llm_status == "available":
                    await self._notify_progress("✅ Server warm-up complete!")
                    return True
                
                # Log intermediate states
                await self._notify_progress(
                    f"⏳ Warm-up {poll_num+1}/{max_polls}: ANN {self.state.ann_status}, LLM {self.state.llm_status}"
                )
                
                # Wait before next poll (exponential backoff)
                await asyncio.sleep(2 ** min(poll_num, 3))  # Max 8 second wait
                
            except Exception as e:
                logger.error(f"Warm-up poll {poll_num} failed: {e}")
                await asyncio.sleep(1)
        
        return False
    
    async def _load_capabilities(self) -> bool:
        """Load server capabilities
        
        Returns:
            True if capabilities loaded successfully
        """
        try:
            caps = await self.api_client.load_capabilities()
            self.state.capabilities_ok = True
            self.state.capabilities = caps

            # Support both historical nested payloads and current flat payloads.
            payload = caps.get("capabilities", caps) if isinstance(caps, dict) else {}
            families = payload.get("supported_families") or payload.get("supported_antenna_families") or []
            freq_range = payload.get("frequency_range_ghz", {})
            bw_range = payload.get("bandwidth_range_mhz", {})
            
            await self._notify_progress(
                f"✅ Capabilities loaded: {len(families)} antenna families, "
                f"freq range {freq_range.get('min', '?')}-{freq_range.get('max', '?')} GHz, "
                f"bandwidth {bw_range.get('min', '?')}-{bw_range.get('max', '?')} MHz"
            )
            return True
            
        except Exception as e:
            logger.error(f"Capabilities load failed: {e}")
            self.state.errors.append(f"Capabilities load failed: {e}")
            await self._notify_progress(f"⚠️ Could not load capabilities: {e}")
            # Don't fail startup for this - continue with fallback
            return True
