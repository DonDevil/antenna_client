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


class AnnDimensions(BaseModel):
    """Predicted antenna dimensions from ANN model"""
    patch_length_mm: float = 0.0
    patch_width_mm: float = 0.0
    patch_height_mm: float = 0.0
    substrate_length_mm: float = 0.0
    substrate_width_mm: float = 0.0
    substrate_height_mm: float = 0.0
    feed_length_mm: float = 0.0
    feed_width_mm: float = 0.0
    feed_offset_x_mm: float = 0.0
    feed_offset_y_mm: float = 0.0


class AnnPrediction(BaseModel):
    """ANN prediction block from server"""
    ann_model_version: str = "unknown"
    confidence: float = 0.0
    dimensions: AnnDimensions = AnnDimensions()


class OptimizeResponse(BaseModel):
    """Response schema from /api/v1/optimize endpoint — matches server schema_version optimize_response.v1"""
    model_config = {"extra": "ignore"}

    schema_version: str = "optimize_response.v1"
    # Server returns: "accepted", "completed", "clarification_required", "error"
    status: str
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    current_stage: Optional[str] = None
    ann_prediction: Optional[AnnPrediction] = None
    command_package: Optional[Dict[str, Any]] = None
    clarification: Optional[Dict[str, Any]] = None
    warnings: list = []
    error: Optional[Dict[str, Any]] = None

    @property
    def error_message(self) -> Optional[str]:
        """Compatibility shim — extract message from error dict."""
        if self.error is None:
            return None
        if isinstance(self.error, dict):
            return self.error.get("message") or self.error.get("error_code") or str(self.error)
        return str(self.error)


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
        
        if response.status in ("accepted", "completed") and response.command_package:
            result["action"] = "execute"
            result["data"] = response.command_package
            result["message"] = "Ready to execute design"
            logger.info(f"Server returned command package (status={response.status})")

        elif response.status in ("accepted", "completed") and not response.command_package:
            result["action"] = "accepted"
            result["message"] = "Design accepted by server (no command package yet)"
            logger.info(f"Server accepted design without command package (status={response.status})")

        elif response.status == "clarification_required":
            result["action"] = "clarify"
            clarification = response.clarification
            if isinstance(clarification, dict):
                result["message"] = clarification.get("reason") or str(clarification)
            else:
                result["message"] = clarification or "Server needs clarification"
            logger.info(f"Server requesting clarification: {result['message']}")

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
