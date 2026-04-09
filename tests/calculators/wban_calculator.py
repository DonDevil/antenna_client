"""WBAN (Wearable Body Area Network) Patch Antenna Calculator

WBAN antennas operate close to human body, requiring:
- Frequency upshift compensation (design frequency 3-10% above target)
- Body detuning modeling
- SAR (Specific Absorption Rate) constraints
- On-body and off-body performance prediction

NOTE: Test implementation only. Server performs production calculations.
"""

import math
from dataclasses import dataclass
from typing import Optional, Dict, Tuple


@dataclass
class BodyProperties:
    """Human body tissue properties at RF"""
    distance_mm: float  # Distance from skin surface
    bending_radius_mm: Optional[float] = None  # Bending radius if worn on curved surface
    tissue_epsilon_r: float = 40.0  # Approximate at 2.4 GHz
    tissue_sigma_s_m: float = 1.5  # Conductivity S/m
    
    def validate(self) -> bool:
        """Validate body properties"""
        return (2.0 <= self.distance_mm <= 50.0 and
                (self.bending_radius_mm is None or self.bending_radius_mm >= 10.0) and
                self.tissue_epsilon_r >= 10.0 and
                self.tissue_sigma_s_m > 0.0)


@dataclass
class WBANDesignParameters:
    """WBAN-specific design parameters"""
    length_mm: float
    width_mm: float
    feed_width_mm: float
    feed_offset_y_mm: float
    ground_slot_length_mm: float
    ground_slot_width_mm: float
    substrate_length_mm: float
    substrate_width_mm: float
    
    def validate(self) -> bool:
        """Validate WBAN parameters"""
        return (self.length_mm > 0 and self.width_mm > 0 and
                self.feed_width_mm > 0 and
                0 < self.feed_offset_y_mm < self.length_mm and
                0 < self.ground_slot_length_mm < self.length_mm and
                0 < self.ground_slot_width_mm < self.width_mm)


@dataclass
class WBANPerformance:
    """WBAN performance in multiple scenarios"""
    # Free space
    resonant_frequency_free_space_ghz: float
    gain_free_space_dbi: float
    efficiency_free_space_pct: float
    
    # On-body (near skin)
    resonant_frequency_on_body_ghz: float
    gain_on_body_dbi: float
    efficiency_on_body_pct: float
    
    # Detuning
    frequency_shift_mhz: float  # Shift when on body
    detuning_pct: float  # Percentage shift
    
    # Safety
    sar_1g_w_kg: float  # SAR averaged over 1g
    sar_10g_w_kg: float  # SAR averaged over 10g
    
    # Return loss
    return_loss_on_body_db: float
    vswr_on_body: float
    
    def is_safe(self, sar_1g_limit: float = 1.6, sar_10g_limit: float = 2.0) -> bool:
        """Check if SAR meets regulatory limits"""
        return self.sar_1g_w_kg <= sar_1g_limit and self.sar_10g_w_kg <= sar_10g_limit
    
    def meets_performance_targets(
        self,
        min_efficiency: float = 50.0,
        max_detuning: float = 8.0,
    ) -> bool:
        """Check if design meets performance targets"""
        return (self.efficiency_on_body_pct >= min_efficiency and
                self.detuning_pct <= max_detuning)


class WBANCalculator:
    """Calculate WBAN antenna parameters and performance"""
    
    C = 3e8  # m/s
    C_MM_PER_NS = 300  # mm/ns
    
    def __init__(self):
        """Initialize WBAN calculator"""
        # WBAN frequency compensation factors
        self.freq_compensation_min = 0.03  # 3% minimum upshift
        self.freq_compensation_max = 0.10  # 10% maximum upshift
        self.freq_compensation_nominal = 0.06  # 6% typical upshift
    
    def calculate_design_frequency(
        self,
        target_frequency_ghz: float,
        body_distance_mm: float = 5.0,
        compensation_type: str = "nominal",
    ) -> float:
        """Calculate design frequency accounting for body detuning
        
        CRITICAL: Design frequency must be HIGHER than target
        because body proximity lowers resonant frequency
        
        Args:
            target_frequency_ghz: Device operating frequency
            body_distance_mm: Distance from skin (affects detuning)
            compensation_type: "minimal", "nominal", or "maximal"
            
        Returns:
            Design frequency in GHz for CST simulation
            
        Raises:
            ValueError: If parameters invalid
        """
        if target_frequency_ghz <= 0:
            raise ValueError(f"Target frequency must be positive: {target_frequency_ghz}")
        if body_distance_mm < 2.0 or body_distance_mm > 50.0:
            raise ValueError(f"Body distance out of range: {body_distance_mm} mm")
        
        # Compensation factor based on distance
        # Closer to body = more detuning = higher compensation needed
        if body_distance_mm < 5.0:
            base_compensation = self.freq_compensation_max
        elif body_distance_mm > 15.0:
            base_compensation = self.freq_compensation_min
        else:
            # Linear interpolation
            base_compensation = (
                self.freq_compensation_min +
                (self.freq_compensation_max - self.freq_compensation_min) *
                (15.0 - body_distance_mm) / 10.0
            )
        
        # Apply type override
        compensation_map = {
            "minimal": self.freq_compensation_min,
            "nominal": self.freq_compensation_nominal,
            "maximal": self.freq_compensation_max,
        }
        
        if compensation_type not in compensation_map:
            raise ValueError(f"Invalid type: {compensation_type}")
        
        if compensation_type != "nominal":
            base_compensation = compensation_map[compensation_type]
        
        design_frequency_ghz = target_frequency_ghz * (1.0 + base_compensation)
        return design_frequency_ghz
    
    def calculate_dimensions(
        self,
        design_frequency_ghz: float,
        substrate_height_mm: float,
        epsilon_r: float,
        body_properties: BodyProperties,
    ) -> WBANDesignParameters:
        """Calculate WBAN antenna dimensions
        
        Based on rectangular patch formulas with WBAN-specific modifications:
        - Ground slot for bandwidth improvement
        - Inset feed for body detuning compensation
        
        Args:
            design_frequency_ghz: Design frequency (pre-compensated)
            substrate_height_mm: Substrate thickness
            epsilon_r: Substrate permittivity
            body_properties: Body parameters for tuning
            
        Returns:
            WBAN design parameters
            
        Raises:
            ValueError: If inputs invalid
        """
        if not body_properties.validate():
            raise ValueError(f"Invalid body properties: {body_properties}")
        
        # Fundamental wavelength
        wavelength_mm = 300.0 / design_frequency_ghz
        
        # Width calculation (similar to rectangular patch)
        denominator = 2 * design_frequency_ghz * math.sqrt((epsilon_r + 1) / 2)
        width_mm = 300.0 / denominator
        
        # Effective permittivity
        eeff = self._calculate_eeff_with_body(
            epsilon_r, width_mm, substrate_height_mm, body_properties
        )
        
        # Length calculation with body effect
        leff_denominator = 2 * design_frequency_ghz * math.sqrt(eeff)
        leff_mm = 300.0 / leff_denominator
        
        # Delta L accounting for body influence
        delta_l_free = self._calculate_delta_l(epsilon_r, width_mm, substrate_height_mm, eeff)
        delta_l_body = delta_l_free * (1.0 + 0.05)  # 5% increase due to body
        
        length_mm = leff_mm - 2 * delta_l_body
        
        # Feed design (more careful for WBAN due to body coupling)
        feed_width_mm = self._calculate_feed_width(wavelength_mm)
        feed_offset_mm = self._calculate_feed_offset(length_mm, width_mm, body_properties)
        
        # Ground slot for bandwidth improvement and decoupling from body
        ground_slot_length_mm = 0.3 * length_mm
        ground_slot_width_mm = 0.08 * width_mm
        
        # Substrate and ground
        substrate_length_mm = length_mm + 6 * substrate_height_mm
        substrate_width_mm = width_mm + 6 * substrate_height_mm
        
        params = WBANDesignParameters(
            length_mm=length_mm,
            width_mm=width_mm,
            feed_width_mm=feed_width_mm,
            feed_offset_y_mm=feed_offset_mm,
            ground_slot_length_mm=ground_slot_length_mm,
            ground_slot_width_mm=ground_slot_width_mm,
            substrate_length_mm=substrate_length_mm,
            substrate_width_mm=substrate_width_mm,
        )
        
        if not params.validate():
            raise ValueError(f"Invalid WBAN parameters: {params}")
        
        return params
    
    def predict_on_body_performance(
        self,
        design_frequency_ghz: float,
        target_frequency_ghz: float,
        dimensions: WBANDesignParameters,
        substrate_epsilon_r: float,
        body_properties: BodyProperties,
        transmitted_power_dbm: float = 0.0,
    ) -> WBANPerformance:
        """Predict WBAN performance when worn on body
        
        Args:
            design_frequency_ghz: CST design frequency
            target_frequency_ghz: Target operating frequency
            dimensions: WBAN dimensions
            substrate_epsilon_r: Substrate permittivity
            body_properties: Body parameters
            transmitted_power_dbm: Transmitted power for SAR calculation
            
        Returns:
            WBANPerformance with all metrics
        """
        # Free space performance (simplified)
        gain_free_space_dbi = 4.0
        efficiency_free_space_pct = 85.0
        resonant_frequency_free_space_ghz = design_frequency_ghz
        
        # On-body frequency shift (empirical model)
        # Body causes downward shift of 2-8% depending on distance
        freq_shift_fraction = self._calculate_body_detuning_fraction(body_properties)
        resonant_frequency_on_body_ghz = design_frequency_ghz * (1.0 - freq_shift_fraction)
        frequency_shift_mhz = (design_frequency_ghz - resonant_frequency_on_body_ghz) * 1000
        detuning_pct = freq_shift_fraction * 100
        
        # Gain reduction on body
        # Body absorbs radiation, gain typically reduced to 2-6 dBi
        gain_on_body_dbi = max(1.0, gain_free_space_dbi - (2.0 + freq_shift_fraction * 10))
        
        # Efficiency reduction (body loss + detuning)
        body_loss_factor = math.exp(-body_properties.tissue_sigma_s_m * body_properties.distance_mm / 1000)
        efficiency_on_body_pct = efficiency_free_space_pct * body_loss_factor * (1.0 - detuning_pct / 100)
        efficiency_on_body_pct = max(30.0, efficiency_on_body_pct)
        
        # Return loss degradation (due to impedance mismatch from detuning)
        rl_degradation_db = 3.0 + detuning_pct / 2
        return_loss_on_body_db = -10.0 - rl_degradation_db
        
        # VSWR
        s11 = 10 ** (return_loss_on_body_db / 20)
        vswr_on_body = (1 + s11) / (1 - s11 + 1e-6)
        
        # SAR calculation (simplified model)
        # SAR ∝ Power / (density × distance²)
        transmitted_power_w = 10 ** (transmitted_power_dbm / 10) / 1000
        tissue_density_kg_m3 = 1000  # Approximate human tissue
        
        sar_base = transmitted_power_w / (tissue_density_kg_m3 * (body_properties.distance_mm / 1000) ** 2)
        # 1g SAR is from smaller averaging volume (higher value)
        # 10g SAR is from larger averaging volume (lower value, more averaged)
        sar_1g_w_kg = sar_base * 5  # Empirical scaling for 1g
        sar_10g_w_kg = sar_base * 1  # Empirical scaling for 10g (more averaged = lower)
        
        return WBANPerformance(
            resonant_frequency_free_space_ghz=resonant_frequency_free_space_ghz,
            gain_free_space_dbi=gain_free_space_dbi,
            efficiency_free_space_pct=efficiency_free_space_pct,
            resonant_frequency_on_body_ghz=resonant_frequency_on_body_ghz,
            gain_on_body_dbi=gain_on_body_dbi,
            efficiency_on_body_pct=efficiency_on_body_pct,
            frequency_shift_mhz=frequency_shift_mhz,
            detuning_pct=detuning_pct,
            sar_1g_w_kg=max(0.0, sar_1g_w_kg),
            sar_10g_w_kg=max(0.0, sar_10g_w_kg),
            return_loss_on_body_db=return_loss_on_body_db,
            vswr_on_body=vswr_on_body,
        )
    
    def account_for_bending(
        self,
        dimensions: WBANDesignParameters,
        bending_radius_mm: float,
    ) -> Dict[str, float]:
        """Account for antenna bending effects when worn on curved surfaces
        
        Args:
            dimensions: Nominal dimensions
            bending_radius_mm: Bending radius of form (e.g., arm radius)
            
        Returns:
            Frequency shift and dimension changes
        """
        if bending_radius_mm < dimensions.length_mm * 1.5:
            raise ValueError(
                f"Bending radius {bending_radius_mm} too small for antenna length {dimensions.length_mm}"
            )
        
        # Bending causes:
        # 1. Stretch/compression of patch dimensions
        # 2. Frequency shift (typically upward for compression)
        arc_angle_rad = dimensions.length_mm / bending_radius_mm
        compression_factor = math.cos(arc_angle_rad)
        
        freq_shift_due_to_bending_pct = (1.0 - compression_factor) * 2.0  # Empirical
        
        return {
            "compression_factor": compression_factor,
            "frequency_shift_pct": freq_shift_due_to_bending_pct,
            "length_change_pct": (compression_factor - 1.0) * 100,
        }
    
    def _calculate_eeff_with_body(
        self,
        epsilon_r: float,
        width_mm: float,
        height_mm: float,
        body_properties: BodyProperties,
    ) -> float:
        """Calculate effective permittivity with body influence"""
        # Free-space eeff
        term1 = (epsilon_r + 1) / 2
        term2 = (epsilon_r - 1) / 2
        fringing = 1 / (1 + 12 * height_mm / width_mm) ** 0.5
        eeff_free = term1 + term2 * fringing
        
        # Body coupling increases effective permittivity
        coupling_factor = 1.0 + (body_properties.tissue_epsilon_r / epsilon_r) * 0.1
        eeff_body = eeff_free * coupling_factor
        
        return max(1.0, eeff_body)
    
    def _calculate_delta_l(
        self,
        epsilon_r: float,
        width_mm: float,
        height_mm: float,
        eeff: float,
    ) -> float:
        """Calculate fringing effect length shortening"""
        h = height_mm
        w = width_mm
        
        numerator = 0.412 * h * (eeff + 0.3) * (w / h + 0.264)
        denominator = (eeff - 0.258) * (w / h + 0.8)
        
        delta_l = numerator / (denominator + 1e-6)
        return max(0.0, delta_l)
    
    def _calculate_feed_width(self, wavelength_mm: float) -> float:
        """Calculate microstrip feed width"""
        return max(0.1, 0.05 * wavelength_mm)
    
    def _calculate_feed_offset(
        self,
        length_mm: float,
        width_mm: float,
        body_properties: BodyProperties,
    ) -> float:
        """Calculate inset feed offset with body detuning compensation"""
        # Base offset for 50 ohm matching
        base_offset_fraction = 0.30
        base_offset = base_offset_fraction * length_mm
        
        # Adjust for body proximity (closer body needs more offset for compensation)
        proximity_factor = (50.0 - body_properties.distance_mm) / 50.0
        adjustment = proximity_factor * 0.05 * length_mm
        
        feed_offset = base_offset + adjustment
        return max(0.5, feed_offset)
    
    def _calculate_body_detuning_fraction(self, body_properties: BodyProperties) -> float:
        """Calculate frequency shift fraction due to body proximity
        
        Empirical model based on distance and tissue properties
        """
        # Base detuning: 5% at 5mm, 2% at 20mm
        if body_properties.distance_mm < 5.0:
            detuning = 0.08
        elif body_properties.distance_mm > 20.0:
            detuning = 0.02
        else:
            # Linear interpolation
            detuning = 0.08 - (body_properties.distance_mm - 5.0) * 0.06 / 15.0
        
        # Conductivity effect (higher conductivity = more detuning)
        sigma_factor = body_properties.tissue_sigma_s_m / 1.5  # Normalized
        detuning *= sigma_factor
        
        return max(0.01, min(0.15, detuning))  # Clamp to reasonable range
