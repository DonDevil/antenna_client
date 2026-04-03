"""
RequestBuilder - Build optimization requests from user intent and design specs

Responsible for:
- Converting design specs → OptimizeRequest
- Building design constraints
- Attaching client capabilities
- Matching antenna_server schema exactly
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel
from utils.validators import extract_frequency_bandwidth


class OptimizeRequest(BaseModel):
    """Request schema for /api/v1/optimize endpoint - MUST match antenna_server schema"""
    schema_version: str
    user_request: str
    target_spec: Dict[str, Any]
    design_constraints: Dict[str, Any]
    optimization_policy: Dict[str, Any]
    runtime_preferences: Dict[str, Any]
    client_capabilities: Dict[str, Any]
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class RequestBuilder:
    """Construct optimization requests matching antenna_server schema"""
    
    def __init__(self):
        """Initialize request builder"""
        self.capabilities = {
            "supports_farfield_export": True,
            "supports_current_distribution_export": True,
            "supports_parameter_sweep": True,
            "max_simulation_timeout_sec": 600,
            "export_formats": ["json", "csv", "txt"]
        }
    
    def build_optimize_request(
        self,
        user_text: str,
        design_specs: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> OptimizeRequest:
        """Build optimization request matching antenna_server schema
        
        Args:
            user_text: User's natural language request
            design_specs: Current design specifications
            context: Conversation context
            
        Returns:
            OptimizeRequest ready to send to server
        """
        freq, bw = extract_frequency_bandwidth(user_text)
        
        # Build with extracted specs
        target_spec = self._build_target_spec(freq, bw, design_specs)
        design_constraints = self._build_design_constraints()
        optimization_policy = self._build_optimization_policy()
        runtime_preferences = self._build_runtime_preferences()
        
        return OptimizeRequest(
            schema_version="optimize_request.v1",
            user_request=user_text,
            target_spec=target_spec,
            design_constraints=design_constraints,
            optimization_policy=optimization_policy,
            runtime_preferences=runtime_preferences,
            client_capabilities=self.capabilities,
            session_id=None,
            context=context or {}
        )
    
    def _build_target_spec(
        self,
        frequency: Optional[float],
        bandwidth: Optional[float],
        design_specs: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Build target specification - matches antenna_server schema
        
        Required: frequency_ghz, bandwidth_mhz
        """
        spec = {
            "frequency_ghz": frequency or 2.4,
            "bandwidth_mhz": bandwidth or 200,  # Default ~8% of 2.4 GHz
            "antenna_family": "microstrip_patch",  # Default antenna family
        }
        
        if design_specs:
            spec.update(design_specs)
        
        return spec
    
    def _build_design_constraints(self) -> Dict[str, Any]:
        """Build design constraints - matches antenna_server schema
        
        Required: allowed_materials, allowed_substrates
        Uses actual material names from antenna_server capabilities
        """
        return {
            "allowed_materials": ["Copper (annealed)"],
            "allowed_substrates": ["FR-4 (lossy)"]
        }
    
    def _build_optimization_policy(self) -> Dict[str, Any]:
        """Build optimization policy - matches antenna_server schema
        
        Required: mode, max_iterations, stop_on_first_valid, acceptance, fallback_behavior
        """
        return {
            "mode": "auto_iterate",
            "max_iterations": 15,
            "stop_on_first_valid": False,
            "acceptance": {
                "center_tolerance_mhz": 50,
                "minimum_bandwidth_mhz": 100,
                "maximum_vswr": 2.0,
                "minimum_gain_dbi": 0,
                "minimum_return_loss_db": -20
            },
            "fallback_behavior": "best_effort"
        }
    
    def _build_runtime_preferences(self) -> Dict[str, Any]:
        """Build runtime preferences - matches antenna_server schema
        
        Required: require_explanations, persist_artifacts, llm_temperature, timeout_budget_sec, priority
        """
        return {
            "require_explanations": True,
            "persist_artifacts": True,
            "llm_temperature": 0.5,
            "timeout_budget_sec": 300,
            "priority": "normal"
        }
    
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
