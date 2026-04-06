"""
IntentParser - Local NLP fallback for offline intent parsing

Responsible for:
- Extract intent from user request locally
- Fallback when server is unavailable
- Extract key parameters (frequency, bandwidth, antenna type)
"""

import re
from typing import Dict, Any, Optional, Tuple
from utils.logger import get_logger


logger = get_logger(__name__)


class IntentParser:
    """Local intent parsing for offline mode"""
    
    ANTENNA_TYPES = [
        "patch", "microstrip", "rectangular",
        "helical", "spiral",
        "horn", "pyramidal", "conical",
        "log periodic", "yagi", "dipole",
        "monopole", "parabolic"
    ]
    
    def parse(self, text: str) -> Dict[str, Any]:
        """Parse user intent from text
        
        Args:
            text: User request text
            
        Returns:
            Dictionary with extracted intent and parameters
        """
        text_lower = text.lower()
        
        intent = {
            "action": self._extract_action(text_lower),
            "antenna_type": self._extract_antenna_type(text_lower),
            "frequency_ghz": self._extract_frequency(text),
            "bandwidth_mhz": self._extract_bandwidth(text),
            "constraints": self._extract_constraints(text_lower),
            "confidence": 0.0
        }
        
        # Calculate confidence
        intent["confidence"] = self._calculate_confidence(intent)
        
        logger.debug(f"Parsed intent: {intent}")
        return intent
    
    def _extract_action(self, text: str) -> str:
        """Extract action from text
        
        Args:
            text: Lowercased user text
            
        Returns:
            Action type (design, optimize, analyze, etc.)
        """
        if any(w in text for w in ["design", "create", "make", "build"]):
            return "design"
        elif any(w in text for w in ["optimize", "improve", "refine"]):
            return "optimize"
        elif any(w in text for w in ["analyze", "check", "test"]):
            return "analyze"
        elif any(w in text for w in ["compare", "versus", "vs"]):
            return "compare"
        else:
            return "design"  # Default action
    
    def _extract_antenna_type(self, text: str) -> Optional[str]:
        """Extract antenna type from text
        
        Args:
            text: Lowercased user text
            
        Returns:
            Antenna type or None
        """
        for ant_type in self.ANTENNA_TYPES:
            if ant_type in text:
                return ant_type.split()[0]  # Return first word
        return None
    
    def _extract_frequency(self, text: str) -> Optional[float]:
        """Extract frequency from text
        
        Args:
            text: User text (case-insensitive)
            
        Returns:
            Frequency in GHz or None
        """
        # Pattern: "2.4 GHz" or "2400 MHz"
        pattern = r'(\d+\.?\d*)\s*(ghz|mhz)'
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower()
            
            # Only return first frequency match
            if unit == "mhz" and value > 100:  # Likely frequency in MHz
                return value / 1000
            elif unit == "ghz":
                return value
        
        return None
    
    def _extract_bandwidth(self, text: str) -> Optional[float]:
        """Extract bandwidth from text
        
        Args:
            text: User text (case-insensitive)
            
        Returns:
            Bandwidth in MHz or None
        """
        # Pattern: "50 MHz" or "100MHz bandwidth"
        pattern = r'(?:bandwidth|bw)[\s:]*(\d+\.?\d*)\s*(mhz|ghz)'
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower()
            return value * 1000 if unit == "ghz" else value
        
        # Alternative: "<number> MHz"
        pattern = r'(\d+(?:\.\d+)?)\s*(?:mhz|megahertz)'
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            return float(match.group(1))
        
        return None
    
    def _extract_constraints(self, text: str) -> Dict[str, Any]:
        """Extract constraints from text
        
        Args:
            text: Lowercased user text
            
        Returns:
            Dictionary of constraints
        """
        constraints = {}
        
        # VSWR constraint
        vswr_pattern = r'vswr\s*(?:=|<|≤)?\s*(\d+\.?\d*)'
        vswr_match = re.search(vswr_pattern, text)
        if vswr_match:
            constraints["max_vswr"] = float(vswr_match.group(1))
        
        # Gain constraint
        gain_pattern = r'gain\s*(?:of|=|>|≥)?\s*(\d+\.?\d*)\s*(?:dbi|db)'
        gain_match = re.search(gain_pattern, text)
        if gain_match:
            constraints["target_gain_dbi"] = float(gain_match.group(1))
        
        # Size constraint
        if "compact" in text or "small" in text:
            constraints["size"] = "compact"
        elif "large" in text or "high gain" in text:
            constraints["size"] = "large"
        
        return constraints
    
    def _calculate_confidence(self, intent: Dict[str, Any]) -> float:
        """Calculate parsing confidence score
        
        Args:
            intent: Parsed intent dictionary
            
        Returns:
            Confidence score 0.0-1.0
        """
        score = 0.0
        
        if intent["action"]:
            score += 0.2
        if intent["antenna_type"]:
            score += 0.2
        if intent["frequency_ghz"]:
            score += 0.25
        if intent["bandwidth_mhz"]:
            score += 0.25
        if intent["constraints"]:
            score += 0.1
        
        return min(score, 1.0)
