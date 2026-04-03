"""
Validators - Schema validation and parameter checking

Responsible for:
- JSON schema validation
- Parameter range checking
- CST project structure verification
"""

from typing import Dict, Any, List
from pydantic import BaseModel, field_validator
import re


class DesignSpecification(BaseModel):
    """Schema for antenna design specifications"""
    
    antenna_family: str  # e.g., "patch", "helical", "horn"
    frequency_ghz: float
    bandwidth_mhz: float
    constraints: Dict[str, Any] = {}
    
    @field_validator('frequency_ghz')
    def validate_frequency(cls, v):
        if v <= 0 or v > 300:
            raise ValueError("Frequency must be between 0 and 300 GHz")
        return v
    
    @field_validator('bandwidth_mhz')
    def validate_bandwidth(cls, v):
        if v <= 0 or v > 10000:
            raise ValueError("Bandwidth must be between 0 and 10000 MHz")
        return v


class CommandPackage(BaseModel):
    """Schema for command package from server"""
    
    package_version: str
    commands: List[Dict[str, Any]]
    policy: Dict[str, Any] = {}


def validate_design_spec(spec: Dict[str, Any]) -> bool:
    """Validate design specification
    
    Args:
        spec: Design specification dict
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If validation fails
    """
    try:
        DesignSpecification(**spec)
        return True
    except Exception as e:
        raise ValueError(f"Invalid design specification: {e}")


def validate_command_package(package: Dict[str, Any]) -> bool:
    """Validate command package structure
    
    Args:
        package: Command package dict
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If validation fails
    """
    try:
        CommandPackage(**package)
        return True
    except Exception as e:
        raise ValueError(f"Invalid command package: {e}")


def extract_frequency_bandwidth(text: str) -> tuple[float, float]:
    """Extract frequency and bandwidth from natural language
    
    Examples:
        "2.4 GHz with 50 MHz bandwidth" -> (2.4, 50.0)
        "5 GHz, 100 MHz BW" -> (5.0, 100.0)
    
    Args:
        text: User request text
        
    Returns:
        Tuple of (frequency_ghz, bandwidth_mhz) or (None, None) if not found
    """
    # Match frequency patterns: "2.4 GHz" or "2400 MHz"
    freq_pattern = r'(\d+\.?\d*)\s*(ghz|mhz)'
    freq_matches = re.finditer(freq_pattern, text, re.IGNORECASE)
    
    frequency = None
    bandwidth = None
    
    for match in freq_matches:
        value = float(match.group(1))
        unit = match.group(2).lower()
        
        if unit == "mhz" and value > 100:  # Likely frequency in MHz
            frequency = value / 1000  # Convert to GHz
        elif unit == "ghz":
            frequency = value
        elif "bandwidth" in text.lower() or "bw" in text.lower():
            bandwidth = value
    
    # Match bandwidth patterns: "50 MHz" or "0.1 GHz"
    bw_pattern = r'(?:bandwidth|bw).*?(\d+\.?\d*)\s*(mhz|ghz)'
    bw_match = re.search(bw_pattern, text, re.IGNORECASE)
    if bw_match:
        value = float(bw_match.group(1))
        unit = bw_match.group(2).lower()
        bandwidth = value * 1000 if unit == "ghz" else value
    
    return (frequency, bandwidth)
