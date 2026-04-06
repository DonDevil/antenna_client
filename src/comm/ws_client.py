"""WebSocket client for real-time session streaming."""

from __future__ import annotations

import asyncio
import json
from typing import Callable, Optional, Any

import websockets
from websockets.client import WebSocketClientProtocol

from utils.logger import get_logger


logger = get_logger(__name__)


class SessionEventListener:
    """Handles WebSocket session event streaming."""

    def __init__(self, base_url: str = "ws://localhost:8000"):
        """Initialize WebSocket listener
        
        Args:
            base_url: Base WebSocket URL
        """
        self.base_url = base_url
        self.connection: Optional[WebSocketClientProtocol] = None
        self.running = False
        self.event_handlers: dict[str, list[Callable]] = {}
        self.error_handlers: list[Callable] = []

    def on_event(self, event_type: str, handler: Callable) -> None:
        """Register handler for specific event type
        
        Args:
            event_type: Event type to listen for (e.g., "iteration.completed")
            handler: Async callable(event_data) to handle event
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    def on_error(self, handler: Callable) -> None:
        """Register error handler
        
        Args:
            handler: Async callable(error) to handle errors
        """
        self.error_handlers.append(handler)

    async def connect(self, session_id: str) -> bool:
        """Connect to session stream and start listening
        
        Args:
            session_id: Session ID to stream events for
            
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            ws_url = f"{self.base_url}/api/v1/sessions/{session_id}/stream"
            logger.info(f"Connecting to WebSocket: {ws_url}")
            
            self.connection = await websockets.connect(ws_url)
            self.running = True
            logger.info(f"Connected to session stream: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            self.running = False
            await self._call_error_handlers(e)
            return False

    async def listen(self) -> None:
        """Listen for events from WebSocket
        
        Blocks until connection closes or error occurs.
        Should be called in separate task.
        """
        if not self.connection:
            logger.error("Not connected to WebSocket")
            return

        try:
            async for message in self.connection:
                try:
                    event_data = json.loads(message)
                    await self._handle_event(event_data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse WebSocket message: {e}")
                    
        except Exception as e:
            logger.error(f"WebSocket listener error: {e}")
            await self._call_error_handlers(e)
        finally:
            self.running = False
            if self.connection:
                await self.connection.close()

    async def disconnect(self) -> None:
        """Disconnect from WebSocket"""
        self.running = False
        if self.connection:
            await self.connection.close()
            logger.info("Disconnected from WebSocket")

    async def _handle_event(self, event_data: dict[str, Any]) -> None:
        """Handle incoming event
        
        Args:
            event_data: Event data from server
        """
        event_type = event_data.get("event_type", "unknown")
        logger.debug(f"Received event: {event_type}")
        
        # Call registered handlers for this event type
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(event_data)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")
                    await self._call_error_handlers(e)

    async def _call_error_handlers(self, error: Exception) -> None:
        """Call all registered error handlers
        
        Args:
            error: Exception that occurred
        """
        for handler in self.error_handlers:
            try:
                await handler(error)
            except Exception as e:
                logger.error(f"Error in error handler: {e}")


class WebSocketClient:
    """High-level WebSocket client factory and manager."""

    def __init__(self, base_url: str = "ws://localhost:8000"):
        """Initialize WebSocket client
        
        Args:
            base_url: Base WebSocket URL
        """
        self.base_url = base_url

    def create_listener(self) -> SessionEventListener:
        """Create new session event listener
        
        Returns:
            SessionEventListener instance
        """
        return SessionEventListener(self.base_url)
