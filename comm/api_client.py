"""
ApiClient - REST API wrapper for antenna_server

Responsible for:
- High-level API methods
- Request/response marshalling
- Schema validation
- Error handling
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, ValidationError
from comm.server_connector import ServerConnector
from utils.logger import get_logger


logger = get_logger(__name__)


class OptimizeRequest(BaseModel):
    """Request schema for optimization endpoint"""
    user_request: str
    context: Optional[Dict[str, Any]] = None


class OptimizeResponse(BaseModel):
    """Response schema for optimization endpoint"""
    status: str
    command_package: Optional[Dict[str, Any]] = None
    clarification: Optional[str] = None


class ApiClient:
    """High-level REST API client for antenna_server"""
    
    def __init__(self, connector: ServerConnector):
        """Initialize API client
        
        Args:
            connector: ServerConnector instance
        """
        self.connector = connector
    
    async def optimize(self, request: OptimizeRequest) -> OptimizeResponse:
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
                json=request.dict()
            )
            return OptimizeResponse(**response_data)
        except ValidationError as e:
            logger.error(f"Invalid optimize response: {e}")
            raise
    
    async def send_feedback(self, feedback: Dict[str, Any]) -> Dict[str, Any]:
        """Send CST measurement feedback to server
        
        Args:
            feedback: Design results and metrics
            
        Returns:
            Server response
        """
        return await self.connector.post(
            "/api/v1/client-feedback",
            json=feedback
        )
    
    async def chat(self, message: str, context: Optional[Dict] = None) -> str:
        """Send chat message
        
        Args:
            message: User message text
            context: Conversation context
            
        Returns:
            Assistant response text
        """
        response_data = await self.connector.post(
            "/api/v1/chat",
            json={"message": message, "context": context or {}}
        )
        return response_data.get("response", "")
    
    async def health_check(self) -> bool:
        """Check server health
        
        Returns:
            True if server is healthy
        """
        try:
            response = await self.connector.get("/api/v1/health")
            return response.get("status") == "healthy"
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False
