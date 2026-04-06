"""Validation helpers and lightweight input extraction for the client."""

from __future__ import annotations

import re
from typing import Dict, Any, List

from pydantic import BaseModel, field_validator


FAMILY_ALIASES = {
    "amc": "amc_patch",
    "amc patch": "amc_patch",
    "microstrip": "microstrip_patch",
    "microstrip patch": "microstrip_patch",
    "rectangular patch": "microstrip_patch",
    "patch": "microstrip_patch",
    "wban": "wban_patch",
    "wban patch": "wban_patch",
}


class DesignSpecification(BaseModel):
    """Schema for antenna design specifications"""
    
    antenna_family: str  # e.g., "patch", "helical", "horn"
    frequency_ghz: float
    bandwidth_mhz: float
    constraints: Dict[str, Any] = {}
    
    @field_validator('frequency_ghz')
    def validate_frequency(cls, v):
        if v <= 0 or v > 100:
            raise ValueError("Frequency must be between 0 and 100 GHz")
        return v
    
    @field_validator('bandwidth_mhz')
    def validate_bandwidth(cls, v):
        if v <= 0 or v > 5000:
            raise ValueError("Bandwidth must be between 0 and 5000 MHz")
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


def extract_antenna_family(text: str) -> str | None:
    """Extract a supported server-side antenna family from free text."""
    low = text.lower()
    for alias, family in sorted(FAMILY_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in low:
            return family
    return None


def extract_frequency_bandwidth(text: str) -> tuple[float | None, float | None]:
    """Extract frequency and bandwidth from natural language.
    
    Examples:
        "2.4 GHz with 50 MHz bandwidth" -> (2.4, 50.0)
        "5 GHz, 100 MHz BW" -> (5.0, 100.0)
    
    Args:
        text: User request text
        
    Returns:
        Tuple of (frequency_ghz, bandwidth_mhz) or (None, None) if not found.
        The first non-bandwidth GHz/MHz token is treated as frequency, while
        explicit "bandwidth"/"bw" phrases are treated as bandwidth.
    """
    low = text.lower()
    frequency = None
    bandwidth = None

    bw_patterns = [
        r'(?:bandwidth|bw)\s*(?:of|=|:|is|around|about|target)?\s*(\d+(?:\.\d+)?)\s*(mhz|ghz)',
        r'(\d+(?:\.\d+)?)\s*(mhz|ghz)\s*(?:bandwidth|bw)',
    ]
    bw_match = None
    for pattern in bw_patterns:
        bw_match = re.search(pattern, low, re.IGNORECASE)
        if bw_match:
            break

    if bw_match:
        value = float(bw_match.group(1))
        unit = bw_match.group(2).lower()
        bandwidth = value * 1000 if unit == "ghz" else value

    bw_span = bw_match.span() if bw_match else None

    freq_pattern = r'(\d+(?:\.\d+)?)\s*(ghz|mhz)'
    for match in re.finditer(freq_pattern, low, re.IGNORECASE):
        if bw_span and match.start() >= bw_span[0] and match.end() <= bw_span[1]:
            continue
        value = float(match.group(1))
        unit = match.group(2).lower()
        if unit == "ghz":
            frequency = value
            break
        if unit == "mhz" and value >= 300:
            frequency = value / 1000.0
            break

    if bandwidth is None:
        trailing_mhz = re.findall(r'(\d+(?:\.\d+)?)\s*mhz', low, re.IGNORECASE)
        if trailing_mhz:
            if frequency is None and len(trailing_mhz) == 1:
                bandwidth = float(trailing_mhz[0])
            elif len(trailing_mhz) >= 2:
                bandwidth = float(trailing_mhz[-1])

    return (frequency, bandwidth)
