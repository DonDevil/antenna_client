"""
Antenna Family Commands - Define request structures for server-side optimization

This module defines the command structure and parameters for each antenna family.
Server performs all calculations; client manages workflow and result extraction.
"""

from typing import Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field


class AntennaFamily(str, Enum):
    """Supported antenna families for server-side optimization"""
    RECT_PATCH = "microstrip_patch"
    AMC_PATCH = "amc_patch"
    WBAN_PATCH = "wban_patch"


class RectPatchCommand(BaseModel):
    """Command for rectangular microstrip patch optimization - server calculates all dimensions"""
    
    antenna_family: str = Field(default=AntennaFamily.RECT_PATCH.value, frozen=True)
    frequency_ghz: float = Field(..., ge=0.1, le=100.0, description="Target frequency")
    bandwidth_mhz: float = Field(default=100.0, ge=10.0, le=5000.0, description="Required bandwidth")
    
    # Shape and feed parameters
    patch_shape: str = Field(default="rectangular", description="Patch shape: rectangular, circular, square")
    feed_type: str = Field(default="edge", description="Feed type: edge, coaxial, proximity-coupled")
    polarization: str = Field(default="linear", description="Polarization: linear, circular")
    
    # Substrate config (server selects appropriate substrate)
    substrate_preference: Optional[str] = Field(
        default=None, 
        description="Substrate hint: Rogers RT/duroid 5880, FR-4, etc (server chooses if None)"
    )
    
    # Performance targets
    min_gain_dbi: Optional[float] = Field(default=None, ge=0.0, le=20.0, description="Minimum gain target")
    min_efficiency_percent: Optional[float] = Field(default=80.0, ge=50.0, le=100.0, description="Minimum efficiency")
    max_vswr: float = Field(default=2.0, ge=1.0, le=5.0, description="Maximum VSWR at center frequency")
    
    class Config:
        json_schema_extra = {
            "example": {
                "antenna_family": "microstrip_patch",
                "frequency_ghz": 2.4,
                "bandwidth_mhz": 100.0,
                "patch_shape": "rectangular",
                "feed_type": "edge",
                "polarization": "linear",
                "min_efficiency_percent": 80.0,
                "max_vswr": 2.0
            }
        }


class AMCPatchCommand(BaseModel):
    """Command for AMC (Artificial Magnetic Conductor) patch optimization
    
    AMC enhances patch gain by +2-3 dB through electromagnetic interaction.
    Server calculates both patch and AMC array parameters.
    """
    
    antenna_family: str = Field(default=AntennaFamily.AMC_PATCH.value, frozen=True)
    frequency_ghz: float = Field(..., ge=0.1, le=100.0, description="Target frequency")
    bandwidth_mhz: float = Field(default=100.0, ge=10.0, le=5000.0, description="Required bandwidth")
    
    # Patch parameters (server optimizes)
    patch_shape: str = Field(default="auto", description="Patch shape: auto (server decides), rectangular, circular")
    feed_type: str = Field(default="auto", description="Feed type: auto, edge, coaxial")
    polarization: str = Field(default="unspecified", description="Polarization hint")
    
    # AMC-specific parameters
    amc_unit_cell_count_per_side: Optional[int] = Field(
        default=7, 
        ge=3, 
        le=15, 
        description="Array size per side (N×N array). Server adjusts if needed."
    )
    amc_air_gap_preference: Optional[str] = Field(
        default="standard",
        description="Air gap preference: standard (λ/4), tight (λ/8), spaced (3λ/8). Server calculates exact."
    )
    
    # Performance targets
    min_gain_improvement_db: Optional[float] = Field(
        default=1.5,
        ge=0.5,
        le=5.0,
        description="Minimum gain improvement over bare patch"
    )
    max_back_lobe_db: Optional[float] = Field(
        default=None,
        ge=-30.0,
        le=0.0,
        description="Maximum back lobe level (more negative = better)"
    )
    
    # Alignment tolerance
    amc_frequency_tolerance_percent: float = Field(
        default=3.0,
        ge=0.5,
        le=10.0,
        description="Allowed frequency mismatch between AMC and patch (critical constraint)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "antenna_family": "amc_patch",
                "frequency_ghz": 2.4,
                "bandwidth_mhz": 100.0,
                "amc_unit_cell_count_per_side": 7,
                "amc_air_gap_preference": "standard",
                "min_gain_improvement_db": 2.0,
                "amc_frequency_tolerance_percent": 3.0
            }
        }


class WBANPatchCommand(BaseModel):
    """Command for WBAN (Wearable Body Area Network) antenna optimization
    
    WBAN designs account for body proximity detuning with 3-10% upshift compensation.
    Server calculates design frequency and validates SAR compliance.
    """
    
    antenna_family: str = Field(default=AntennaFamily.WBAN_PATCH.value, frozen=True)
    
    # Target and operating parameters
    operating_frequency_ghz: float = Field(..., ge=0.1, le=100.0, description="On-body operating frequency")
    bandwidth_mhz: float = Field(default=100.0, ge=10.0, le=5000.0, description="Required bandwidth on-body")
    
    # Body interaction parameters
    body_proximity_mm: Optional[float] = Field(
        default=5.0,
        ge=0.0,
        le=30.0,
        description="Distance from skin (0mm = direct contact)"
    )
    body_tissue_model: Optional[str] = Field(
        default="generic",
        description="Body tissue model: generic, muscle, fat. Server uses for detuning prediction."
    )
    
    # Design frequency compensation (server calculates, user provides hint)
    design_frequency_upshift_percent: Optional[float] = Field(
        default=5.0,
        ge=3.0,
        le=10.0,
        description="Design frequency upshift to compensate for body detuning"
    )
    
    # SAR safety constraints
    sar_limit_w_per_kg_1g: float = Field(
        default=1.6,
        ge=0.1,
        le=2.0,
        description="FCC SAR limit (1g average)"
    )
    sar_limit_w_per_kg_10g: float = Field(
        default=2.0,
        ge=0.1,
        le=10.0,
        description="FCC SAR limit (10g average)"
    )
    
    # Patch parameters
    patch_shape: str = Field(default="auto", description="Patch shape")
    feed_type: str = Field(default="auto", description="Feed type")
    
    # Performance targets
    min_efficiency_on_body_percent: Optional[float] = Field(
        default=50.0,
        ge=20.0,
        le=95.0,
        description="Minimum efficiency on-body (lower than free-space due to losses)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "antenna_family": "wban_patch",
                "operating_frequency_ghz": 2.4,
                "bandwidth_mhz": 100.0,
                "body_proximity_mm": 5.0,
                "design_frequency_upshift_percent": 5.0,
                "sar_limit_w_per_kg_1g": 1.6,
                "min_efficiency_on_body_percent": 50.0
            }
        }


class AntennaCommandFactory:
    """Factory for creating and validating antenna commands"""
    
    _commands = {
        AntennaFamily.RECT_PATCH.value: RectPatchCommand,
        AntennaFamily.AMC_PATCH.value: AMCPatchCommand,
        AntennaFamily.WBAN_PATCH.value: WBANPatchCommand,
    }
    
    @classmethod
    def create_rect_patch_command(
        cls,
        frequency_ghz: float,
        bandwidth_mhz: float = 100.0,
        **kwargs
    ) -> RectPatchCommand:
        """Create rectangular patch command"""
        return RectPatchCommand(
            frequency_ghz=frequency_ghz,
            bandwidth_mhz=bandwidth_mhz,
            **kwargs
        )
    
    @classmethod
    def create_amc_command(
        cls,
        frequency_ghz: float,
        bandwidth_mhz: float = 100.0,
        amc_unit_cell_count_per_side: int = 7,
        **kwargs
    ) -> AMCPatchCommand:
        """Create AMC patch command"""
        return AMCPatchCommand(
            frequency_ghz=frequency_ghz,
            bandwidth_mhz=bandwidth_mhz,
            amc_unit_cell_count_per_side=amc_unit_cell_count_per_side,
            **kwargs
        )
    
    @classmethod
    def create_wban_command(
        cls,
        operating_frequency_ghz: float,
        bandwidth_mhz: float = 100.0,
        body_proximity_mm: float = 5.0,
        **kwargs
    ) -> WBANPatchCommand:
        """Create WBAN patch command"""
        return WBANPatchCommand(
            operating_frequency_ghz=operating_frequency_ghz,
            bandwidth_mhz=bandwidth_mhz,
            body_proximity_mm=body_proximity_mm,
            **kwargs
        )
    
    @classmethod
    def get_command_class(cls, family: str):
        """Get command class for family"""
        if family not in cls._commands:
            raise ValueError(f"Unknown antenna family: {family}")
        return cls._commands[family]
    
    @classmethod
    def validate_command(cls, family: str, data: Dict[str, Any]):
        """Validate command data for family"""
        cmd_class = cls.get_command_class(family)
        return cmd_class(**data)
