"""Rectangular Microstrip Patch Antenna Calculator

Implements fundamental equations for rectangular patch design:
- Patch resonance and dimensions
- Feed design and impedance matching
- Substrate effects
- Performance metrics prediction
"""

import math
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple


@dataclass
class SubstrateProperties:
    """Substrate material properties"""
    epsilon_r: float  # Relative permittivity
    height_mm: float  # Substrate thickness
    tan_delta: float = 0.0  # Loss tangent
    
    def validate(self) -> bool:
        """Validate substrate properties"""
        return (1.0 <= self.epsilon_r <= 15.0 and 
                0.1 <= self.height_mm <= 10.0 and
                0.0 <= self.tan_delta <= 0.1)


@dataclass
class RectPatchDimensions:
    """Rectangular patch dimensions"""
    length_mm: float  # Patch length (primary resonance)
    width_mm: float   # Patch width (controls radiation)
    feed_width_mm: float  # Microstrip feed width
    feed_offset_y_mm: float  # Vertical feed offset (toward center)
    substrate_length_mm: float  # Substrate size
    substrate_width_mm: float  # Substrate size
    
    def validate(self) -> bool:
        """Validate dimensions are physically reasonable"""
        return (self.length_mm > 0 and self.width_mm > 0 and
                self.feed_width_mm > 0 and
                0 < self.feed_offset_y_mm < self.length_mm and
                self.substrate_length_mm > self.length_mm and
                self.substrate_width_mm > self.width_mm)


@dataclass
class RectPatchPerformance:
    """Expected performance metrics"""
    resonant_frequency_ghz: float
    return_loss_db: float
    vswr: float
    gain_dbi: float
    bandwidth_mhz: float
    efficiency_pct: float
    
    def is_valid(self, min_return_loss_db: float = -10.0, max_vswr: float = 2.0) -> bool:
        """Check if design meets acceptance criteria"""
        return (self.return_loss_db <= min_return_loss_db and
                self.vswr <= max_vswr and
                self.efficiency_pct >= 40.0)


class RectangularPatchCalculator:
    """Calculate rectangular patch antenna parameters"""
    
    # Physical constants
    C = 3e8  # Speed of light m/s
    C_MM_PER_NS = 300  # mm/ns for convenience
    
    # Numerical fitting parameters from theory
    DELTA_L_CONSTANT = 0.412
    EFF_ALPHA = 0.3
    EFF_BETA = 0.264
    EFF_GAMMA = 0.258
    EFF_DELTA = 0.8
    
    def __init__(self):
        """Initialize calculator"""
        pass
    
    def calculate_dimensions(
        self,
        target_frequency_ghz: float,
        substrate: SubstrateProperties,
        target_bandwidth_mhz: float = 100.0,
    ) -> RectPatchDimensions:
        """Calculate patch dimensions from target frequency
        
        Args:
            target_frequency_ghz: Design frequency
            substrate: Substrate material properties
            target_bandwidth_mhz: Desired bandwidth (influences width selection)
            
        Returns:
            RectPatchDimensions with all required dimensions
            
        Raises:
            ValueError: If inputs are invalid
        """
        if not substrate.validate():
            raise ValueError(f"Invalid substrate properties: {substrate}")
        if target_frequency_ghz <= 0:
            raise ValueError(f"Frequency must be positive: {target_frequency_ghz}")
        
        # Fundamental wavelength in mm (c=3e8 m/s, convert to mm/ns then divide by freq in GHz)
        # wavelength_mm = 300 mm/ns / (freq in GHz)
        wavelength_0_mm = 300.0 / target_frequency_ghz
        
        # Calculate patch width from transmission line theory
        # W = c / (2*f0*sqrt((er+1)/2))
        denominator = 2 * target_frequency_ghz * math.sqrt((substrate.epsilon_r + 1) / 2)
        width_mm = 300.0 / denominator
        
        # Calculate effective permittivity
        eeff = self._calculate_eeff(substrate.epsilon_r, width_mm, substrate.height_mm)
        
        # Calculate length shortening due to fringing fields
        delta_l_mm = self._calculate_delta_l(
            substrate, width_mm, eeff
        )
        
        # Calculate effective length from resonance condition
        # Leff = c / (2*f0*sqrt(eeff))
        leff_denominator = 2 * target_frequency_ghz * math.sqrt(eeff)
        leff_mm = 300.0 / leff_denominator
        
        # Actual patch length
        length_mm = leff_mm - 2 * delta_l_mm
        
        # Microstrip feed width (for ~50 ohm impedance)
        feed_width_mm = self._calculate_feed_width(substrate, wavelength_0_mm)
        
        # Inset feed offset (impedance matching)
        feed_offset_mm = self._calculate_feed_offset(length_mm, width_mm)
        
        # Substrate and ground size (6*h beyond patch edges)
        substrate_length_mm = length_mm + 6 * substrate.height_mm
        substrate_width_mm = width_mm + 6 * substrate.height_mm
        
        dimensions = RectPatchDimensions(
            length_mm=length_mm,
            width_mm=width_mm,
            feed_width_mm=feed_width_mm,
            feed_offset_y_mm=feed_offset_mm,
            substrate_length_mm=substrate_length_mm,
            substrate_width_mm=substrate_width_mm,
        )
        
        if not dimensions.validate():
            raise ValueError(f"Calculated invalid dimensions: {dimensions}")
        
        return dimensions
    
    def predict_performance(
        self,
        target_frequency_ghz: float,
        dimensions: RectPatchDimensions,
        substrate: SubstrateProperties,
    ) -> RectPatchPerformance:
        """Predict antenna performance based on design
        
        Args:
            target_frequency_ghz: Design frequency
            dimensions: Patch dimensions
            substrate: Substrate properties
            
        Returns:
            Expected performance metrics
        """
        # Calculate effective permittivity
        eeff = self._calculate_eeff(
            substrate.epsilon_r, dimensions.width_mm, substrate.height_mm
        )
        
        # Calculate resonant frequency (slightly different due to feed perturbation)
        lambda_eff_mm = 2 * (dimensions.length_mm + 2 * self._calculate_delta_l(
            substrate, dimensions.width_mm, eeff
        )) * math.sqrt(eeff)
        
        resonant_frequency_ghz = 300.0 / lambda_eff_mm
        
        # Impedance matching quality (simplified)
        # Better matching with more inset offset
        feed_quality = min(1.0, dimensions.feed_offset_y_mm / (dimensions.length_mm / 3))
        
        # Estimate return loss (quality factor and matching)
        # Return loss in dB: -20*log10(|S11|)
        # S11 decreases with better matching
        s11 = 0.3 * (1.0 - feed_quality)  # Simplified: ranges from 0.3 to ~0
        return_loss_db = -20 * math.log10(max(0.01, s11))
        return_loss_db = min(-6, return_loss_db)  # Cap at -6 dB (realistic for good match)
        
        # VSWR from return loss
        vswr = (1 + s11) / (max(1e-6, 1 - s11))
        vswr = max(1.0, min(10.0, vswr))  # Clamp to realistic range
        
        # Gain estimation (simplified, ~5-7 dBi for typical patch)
        wavelength_0_mm = 300.0 / target_frequency_ghz
        normalized_area = (dimensions.length_mm / wavelength_0_mm) * (
            dimensions.width_mm / wavelength_0_mm
        )
        gain_dbi = 4.0 + 8.0 * normalized_area  # Empirical fit
        gain_dbi = max(2.0, min(9.0, gain_dbi))
        
        # Bandwidth estimation
        # Narrow-band antenna, typically 2-5% of center frequency
        bandwidth_mhz = target_frequency_ghz * 1000 * 0.03
        
        # Efficiency (affected by substrate loss)
        conductor_loss = 0.98  # ~2% conductor loss
        dielectric_loss = math.exp(
            -substrate.tan_delta * math.pi * target_frequency_ghz
        )
        efficiency_pct = 100 * conductor_loss * dielectric_loss
        efficiency_pct = max(30.0, min(99.0, efficiency_pct))
        
        return RectPatchPerformance(
            resonant_frequency_ghz=resonant_frequency_ghz,
            return_loss_db=return_loss_db,
            vswr=vswr,
            gain_dbi=gain_dbi,
            bandwidth_mhz=bandwidth_mhz,
            efficiency_pct=efficiency_pct,
        )
    
    def _calculate_eeff(
        self, epsilon_r: float, width_mm: float, height_mm: float
    ) -> float:
        """Calculate effective permittivity considering fringing fields"""
        term1 = (epsilon_r + 1) / 2
        term2 = (epsilon_r - 1) / 2
        
        # Fringing field correction
        width_height_ratio = width_mm / height_mm
        denominator = (1 + 12 * height_mm / width_mm) ** 0.5
        fringing = 1 / denominator
        
        eeff = term1 + term2 * fringing
        return max(1.0, eeff)
    
    def _calculate_delta_l(
        self,
        substrate: SubstrateProperties,
        width_mm: float,
        eeff: float,
    ) -> float:
        """Calculate length shortening due to fringing fields"""
        h = substrate.height_mm
        w = width_mm
        er = substrate.epsilon_r
        
        # Numerator
        numerator_term1 = eeff + self.EFF_ALPHA
        numerator_term2 = w / h + self.EFF_BETA
        numerator = self.DELTA_L_CONSTANT * h * numerator_term1 * numerator_term2
        
        # Denominator
        denominator_term1 = eeff - self.EFF_GAMMA
        denominator_term2 = w / h + self.EFF_DELTA
        denominator = denominator_term1 * denominator_term2
        
        delta_l = numerator / (denominator + 1e-6)
        return max(0.0, delta_l)
    
    def _calculate_feed_width(
        self, substrate: SubstrateProperties, wavelength_0_mm: float
    ) -> float:
        """Calculate microstrip feed width for ~50 ohm characteristic impedance"""
        # Simplified empirical formula
        # Feed width typically 0.03 to 0.08 wavelengths
        feed_width_fraction = 0.05
        feed_width_mm = feed_width_fraction * wavelength_0_mm
        return max(0.1, feed_width_mm)
    
    def _calculate_feed_offset(self, length_mm: float, width_mm: float) -> float:
        """Calculate inset feed offset for impedance matching"""
        # Empirical: offset between 20-40% of length
        # Using 30% for nominal 50 ohm matching
        offset_fraction = 0.30
        feed_offset_mm = offset_fraction * length_mm
        return max(0.5, feed_offset_mm)
    
    def calculate_noise_variation(
        self, dimensions: RectPatchDimensions, noise_percent: float = 5.0
    ) -> Dict[str, Tuple[float, float]]:
        """Calculate variation ranges due to manufacturing tolerance
        
        Args:
            dimensions: Nominal dimensions
            noise_percent: Manufacturing tolerance percentage
            
        Returns:
            Dictionary of {parameter: (min, max)} values
        """
        tolerance = noise_percent / 100.0
        
        return {
            "length_mm": (
                dimensions.length_mm * (1 - tolerance),
                dimensions.length_mm * (1 + tolerance),
            ),
            "width_mm": (
                dimensions.width_mm * (1 - tolerance),
                dimensions.width_mm * (1 + tolerance),
            ),
            "feed_width_mm": (
                dimensions.feed_width_mm * (1 - tolerance),
                dimensions.feed_width_mm * (1 + tolerance),
            ),
            "feed_offset_mm": (
                dimensions.feed_offset_y_mm * (1 - tolerance),
                dimensions.feed_offset_y_mm * (1 + tolerance),
            ),
        }
