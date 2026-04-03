"""
ResponseHandler - Parse and handle server responses

Responsible for:
- Parsing OptimizeResponse
- Extracting command packages
- Handling clarification requests
- Processing error responses
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, ValidationError
from utils.logger import get_logger


logger = get_logger(__name__)


class OptimizeResponse(BaseModel):
    """Response schema from /api/v1/optimize endpoint"""
    status: str  # "success", "clarification_required", "error"
    command_package: Optional[Dict[str, Any]] = None
    clarification: Optional[str] = None
    error_message: Optional[str] = None
    next_step: Optional[str] = None


class ResponseHandler:
    """Handle and parse server responses"""
    
    def parse_optimize_response(self, response_data: Dict[str, Any]) -> OptimizeResponse:
        """Parse optimize response from server
        
        Args:
            response_data: Raw response dict from server
            
        Returns:
            OptimizeResponse object
            
        Raises:
            ValidationError: If response doesn't match schema
        """
        try:
            return OptimizeResponse(**response_data)
        except ValidationError as e:
            logger.error(f"Invalid optimize response: {e}")
            raise
    
    def handle_optimize_response(self, response: OptimizeResponse) -> Dict[str, Any]:
        """Process optimize response and return action dict
        
        Args:
            response: Parsed OptimizeResponse
            
        Returns:
            Dictionary with action to take (execute, clarify, etc.)
        """
        result = {
            "action": None,
            "status": response.status,
            "data": None,
            "message": None
        }
        
        if response.status == "success" and response.command_package:
            result["action"] = "execute"
            result["data"] = response.command_package
            result["message"] = "Ready to execute design"
            logger.info("Server returned valid command package")
        
        elif response.status == "clarification_required":
            result["action"] = "clarify"
            result["message"] = response.clarification or "Server needs clarification"
            logger.info(f"Server requesting clarification: {response.clarification}")
        
        elif response.status == "error":
            result["action"] = "error"
            result["message"] = response.error_message or "Unknown error"
            logger.error(f"Server error: {response.error_message}")
        
        return result
    
    def parse_chat_response(self, response_data: Dict[str, Any]) -> str:
        """Parse chat response
        
        Args:
            response_data: Raw chat response dict
            
        Returns:
            Chat message text
        """
        return response_data.get("response", "")
    
    def parse_feedback_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse feedback response
        
        Args:
            response_data: Raw feedback response dict
            
        Returns:
            Feedback response data
        """
        return {
            "accepted": response_data.get("accepted", False),
            "next_iteration": response_data.get("next_iteration"),
            "message": response_data.get("message", "")
        }
