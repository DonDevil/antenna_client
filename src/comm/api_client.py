"""High-level REST API wrapper for the current antenna server."""

from __future__ import annotations

from typing import Dict, Any, Optional

from comm.response_handler import ResponseHandler, OptimizeResponse
from comm.server_connector import ServerConnector
from utils.logger import get_logger


logger = get_logger(__name__)


class ApiClient:
    """High-level REST API client for antenna_server"""
    
    def __init__(self, connector: ServerConnector):
        """Initialize API client
        
        Args:
            connector: ServerConnector instance
        """
        self.connector = connector
        self.response_handler = ResponseHandler()
    
    async def optimize(self, request: Dict[str, Any]) -> OptimizeResponse:
        """Send optimization request
        
        Args:
            request: Optimization request with user intent
            
        Returns:
            OptimizeResponse with command_package or clarification
            
        Raises:
            ValidationError: If response doesn't match schema
        """
        try:
            response_data = await self.connector.post(
                "/api/v1/optimize",
                json=request
            )
            return self.response_handler.parse_optimize_response(response_data)
        except Exception as e:
            logger.error(f"Optimize request failed: {e}")
            raise
    
    async def send_result(self, result_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Post CST result payload to the canonical result endpoint.

        Args:
            result_payload: Extracted CST metrics and artifact references

        Returns:
            Server response
        """
        return await self.connector.post(
            "/api/v1/result",
            json=result_payload
        )

    async def send_feedback(self, feedback: Dict[str, Any]) -> Dict[str, Any]:
        """Backward-compatible alias for posting CST results.

        This keeps existing callers working while the system migrates to
        the explicit result endpoint naming.
        """
        return await self.send_result(feedback)
    
    async def chat(self, message: str, requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send chat message for intent capture and assistant guidance.
        
        Args:
            message: User message text
            requirements: Current extracted requirements
            
        Returns:
            Raw chat payload from the server
        """
        return await self.connector.post(
            "/api/v1/chat",
            json={"message": message, "requirements": requirements or {}}
        )

    async def parse_intent(self, user_request: str) -> Dict[str, Any]:
        """Ask the server to parse intent without starting optimization."""
        response_data = await self.connector.post(
            "/api/v1/intent/parse",
            json={"user_request": user_request},
        )
        return response_data.get("intent_summary", {})

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """Fetch current session state from the server."""
        return await self.connector.get(f"/api/v1/sessions/{session_id}")

    async def load_capabilities(self) -> Dict[str, Any]:
        """Load capability catalog from the server."""
        return await self.connector.get("/api/v1/capabilities")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check server health and return the health payload.
        
        Returns:
            Health payload
        """
        return await self.connector.get("/api/v1/health")
