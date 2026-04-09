"""Antenna family calculators for testing

These are test implementations only. For production use, calculations
are performed server-side. These modules are used during ANN training
and validation until the neural network model is ready.
"""

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
