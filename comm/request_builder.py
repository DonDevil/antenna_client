"""
RequestBuilder - Build optimization requests from user intent and design specs

Responsible for:
- Converting design specs → OptimizeRequest
- Building design constraints
- Attaching client capabilities
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel
from utils.validators import extract_frequency_bandwidth


class OptimizeRequest(BaseModel):
    """Request schema for /api/v1/optimize endpoint"""
    user_request: str
    context: Optional[Dict[str, Any]] = None
    design_specs: Optional[Dict[str, Any]] = None
    client_capabilities: Optional[Dict[str, Any]] = None


class RequestBuilder:
    """Construct optimization requests"""
    
    def __init__(self):
        """Initialize request builder"""
        self.capabilities = {
            "supports_farfield_export": True,
            "supports_current_distribution_export": True,
            "max_simulation_timeout_sec": 600,
            "export_formats": ["json", "csv"]
        }
    
    def build_optimize_request(
        self,
        user_text: str,
        design_specs: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> OptimizeRequest:
        """Build optimization request
        
        Args:
            user_text: User's natural language request
            design_specs: Current design specifications
            context: Conversation context
            
        Returns:
            OptimizeRequest ready to send to server
        """
        return OptimizeRequest(
            user_request=user_text,
            design_specs=design_specs or self._extract_specs_from_text(user_text),
            context=context or {},
            client_capabilities=self.capabilities
        )
    
    def _extract_specs_from_text(self, text: str) -> Dict[str, Any]:
        """Extract design specs from user text
        
        Args:
            text: User request text
            
        Returns:
            Design specs dictionary
        """
        freq, bw = extract_frequency_bandwidth(text)
        
        specs = {}
        if freq:
            specs["frequency_ghz"] = freq
        if bw:
            specs["bandwidth_mhz"] = bw
        
        return specs if specs else None
