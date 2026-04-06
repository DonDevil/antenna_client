"""Build optimize requests that match the current server schema."""

from __future__ import annotations

from typing import Dict, Any, Optional

from pydantic import BaseModel

from utils.validators import extract_antenna_family, extract_frequency_bandwidth


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


FAMILY_DEFAULT_SUBSTRATES = {
    "amc_patch": ["FR-4 (lossy)"],
    "microstrip_patch": ["Rogers RT/duroid 5880"],
    "wban_patch": ["Rogers RO3003"],
}


class RequestBuilder:
    """Construct optimization requests matching antenna_server schema"""
    
    def __init__(self):
        """Initialize request builder"""
        self.capabilities = {
            "supports_farfield_export": True,
            "supports_current_distribution_export": False,
            "supports_parameter_sweep": False,
            "max_simulation_timeout_sec": 600,
            "export_formats": ["json", "csv", "txt"],
        }
    
    def build_optimize_request(
        self,
        user_text: str,
        design_specs: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
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

        # Build with form values as authority, parser as fallback.
        resolved_specs = dict(design_specs or {})
        if not resolved_specs.get("antenna_family"):
            inferred_family = extract_antenna_family(user_text)
            if inferred_family:
                resolved_specs["antenna_family"] = inferred_family

        target_spec = self._build_target_spec(freq, bw, resolved_specs)
        design_constraints = self._build_design_constraints(target_spec["antenna_family"])
        optimization_policy = self._build_optimization_policy(target_spec, resolved_specs)
        runtime_preferences = self._build_runtime_preferences()

        return OptimizeRequest(
            schema_version="optimize_request.v1",
            user_request=user_text,
            target_spec=target_spec,
            design_constraints=design_constraints,
            optimization_policy=optimization_policy,
            runtime_preferences=runtime_preferences,
            client_capabilities=self.capabilities,
            session_id=session_id,
        )
    
    def _build_target_spec(
        self,
        frequency: Optional[float],
        bandwidth: Optional[float],
        design_specs: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Build target specification - matches antenna_server schema
        
        Required: frequency_ghz, bandwidth_mhz, antenna_family
        """
        constraints = (design_specs or {}).get("constraints", {}) if design_specs else {}
        antenna_family = (design_specs or {}).get("antenna_family") or extract_antenna_family((design_specs or {}).get("user_request", "") or "")
        if not antenna_family and design_specs and isinstance(design_specs.get("antenna_family"), str):
            antenna_family = design_specs["antenna_family"]
        if not antenna_family:
            antenna_family = extract_antenna_family((design_specs or {}).get("raw_text", "") or "")
        if not antenna_family:
            antenna_family = extract_antenna_family((design_specs or {}).get("summary", "") or "")
        if not antenna_family:
            antenna_family = "amc_patch"

        spec = {
            "frequency_ghz": float((design_specs or {}).get("frequency_ghz") or frequency or 2.4),
            "bandwidth_mhz": float((design_specs or {}).get("bandwidth_mhz") or bandwidth or 100.0),
            "antenna_family": antenna_family,
        }

        return spec
    
    def _build_design_constraints(self, antenna_family: str) -> Dict[str, Any]:
        """Build design constraints - matches antenna_server schema
        
        Required: allowed_materials, allowed_substrates
        Uses actual material names from antenna_server capabilities
        """
        return {
            "allowed_materials": ["Copper (annealed)"],
            "allowed_substrates": FAMILY_DEFAULT_SUBSTRATES.get(antenna_family, ["FR-4 (lossy)"])
        }
    
    def _build_optimization_policy(self, target_spec: Dict[str, Any], design_specs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build optimization policy - matches antenna_server schema
        
        Required: mode, max_iterations, stop_on_first_valid, acceptance, fallback_behavior
        """
        constraints = (design_specs or {}).get("constraints", {}) if design_specs else {}
        return {
            "mode": "auto_iterate",
            "max_iterations": 5,
            "stop_on_first_valid": True,
            "acceptance": {
                "center_tolerance_mhz": 20,
                "minimum_bandwidth_mhz": float(target_spec["bandwidth_mhz"]),
                "maximum_vswr": float(constraints.get("max_vswr", 2.0)),
                "minimum_gain_dbi": float(constraints.get("target_gain_dbi", 0.0)),
            },
            "fallback_behavior": "best_effort"
        }
    
    def _build_runtime_preferences(self) -> Dict[str, Any]:
        """Build runtime preferences - matches antenna_server schema
        
        Required: require_explanations, persist_artifacts, llm_temperature, timeout_budget_sec, priority
        """
        return {
            "require_explanations": False,
            "persist_artifacts": True,
            "llm_temperature": 0.0,
            "timeout_budget_sec": 300,
            "priority": "normal"
        }
