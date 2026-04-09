"""Antenna family calculation modules for design and optimization."""

from .rect_patch_calculator import (
    RectangularPatchCalculator,
    SubstrateProperties,
    RectPatchDimensions,
    RectPatchPerformance,
)
from .amc_calculator import (
    AMCCalculator,
    UnitCellProperties,
    AMCArrayDimensions,
    AMCPerformance,
)
from .wban_calculator import (
    WBANCalculator,
    BodyProperties,
    WBANDesignParameters,
    WBANPerformance,
)

__all__ = [
    "RectangularPatchCalculator",
    "SubstrateProperties",
    "RectPatchDimensions",
    "RectPatchPerformance",
    "AMCCalculator",
    "UnitCellProperties",
    "AMCArrayDimensions",
    "AMCPerformance",
    "WBANCalculator",
    "BodyProperties",
    "WBANDesignParameters",
    "WBANPerformance",
]
