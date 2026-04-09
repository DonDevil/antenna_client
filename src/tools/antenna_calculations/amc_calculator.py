"""Artificial Magnetic Conductor (AMC) Unit Cell and Array Calculator

AMC provides frequency-selective surfaces for:
- Gain enhancement (2-3 dB)
- Back lobe suppression
- High impedance surface behavior at resonance

Key constraint: AMC resonance frequency MUST match patch frequency (±2-3%)
"""

import math
from dataclasses import dataclass
from typing import Optional, Dict, Tuple


@dataclass
class UnitCellProperties:
    """Unit cell geometric properties"""
    period_mm: float  # Unit cell lattice period
    patch_size_mm: float  # Conductor patch size
    gap_mm: float  # Gap between patches
    
    def validate(self) -> bool:
        """Validate UC geometry"""
        return (self.period_mm > 0 and self.patch_size_mm > 0 and
                self.gap_mm > 0 and
                self.patch_size_mm + self.gap_mm <= self.period_mm * 1.05)


@dataclass
class AMCArrayDimensions:
    """AMC array dimensions"""
    rows: int  # Number of rows
    cols: int  # Number of columns
    period_mm: float
    patch_size_mm: float
    gap_mm: float
    substrate_height_mm: float
    epsilon_r: float
    
    def validate(self) -> bool:
        """Validate array is physically reasonable"""
        return (self.rows >= 3 and self.cols >= 3 and
                self.period_mm > 0 and self.patch_size_mm > 0 and
                self.substrate_height_mm > 0 and
                self.epsilon_r >= 1.0)
    
    def get_array_dimensions_mm(self) -> Tuple[float, float]:
        """Get physical array dimensions"""
        length = self.rows * self.period_mm
        width = self.cols * self.period_mm
        return length, width


@dataclass
class AMCPerformance:
    """Expected AMC performance"""
    resonant_frequency_ghz: float
    reflection_phase_deg: float  # Should be ~0 at resonance
    phase_bandwidth_deg: float  # Range where phase is ±90 deg
    gain_improvement_db: float  # Gain improvement over AMC
    back_lobe_reduction_db: float
    array_efficiency_pct: float
    
    def is_matched_to_patch(
        self, patch_frequency_ghz: float, tolerance_pct: float = 3.0
    ) -> bool:
        """Check if AMC resonance matches patch frequency"""
        freq_error_pct = abs(self.resonant_frequency_ghz - patch_frequency_ghz) / patch_frequency_ghz * 100
        return freq_error_pct <= tolerance_pct


class AMCCalculator:
    """Calculate AMC unit cell and array parameters"""
    
    C = 3e8  # m/s
    C_MM_PER_NS = 300  # mm/ns
    
    def __init__(self):
        """Initialize AMC calculator"""
        self.min_array_size = 3  # Minimum 3x3 array
        self.default_tolerance_pct = 3.0  # Frequency matching tolerance
    
    def calculate_unit_cell(
        self,
        target_frequency_ghz: float,
        substrate_height_mm: float,
        epsilon_r: float,
        wavelength_fraction_min: float = 0.15,
        wavelength_fraction_max: float = 0.30,
    ) -> UnitCellProperties:
        """Calculate AMC unit cell dimensions
        
        This follows the LC network model where frequency is determined by:
        f0 = 1 / (2π√LC)
        
        Larger patches and smaller gaps → lower frequency
        
        Args:
            target_frequency_ghz: Design frequency
            substrate_height_mm: Substrate thickness
            epsilon_r: Relative permittivity
            wavelength_fraction_min: Minimum period as fraction of wavelength
            wavelength_fraction_max: Maximum period as fraction of wavelength
            
        Returns:
            UnitCellProperties with period, patch_size, gap
            
        Raises:
            ValueError: If inputs invalid
        """
        if target_frequency_ghz <= 0:
            raise ValueError(f"Frequency must be positive: {target_frequency_ghz}")
        if substrate_height_mm <= 0 or epsilon_r < 1.0:
            raise ValueError(f"Invalid substrate: h={substrate_height_mm}, er={epsilon_r}")
        
        # Wavelength in mm (using free space, refinement would use substrate)
        wavelength_mm = 300.0 / target_frequency_ghz
        
        # Period selection (typical: 0.15-0.30 wavelengths)
        # Use middle value for nominal design
        period_fraction = (wavelength_fraction_min + wavelength_fraction_max) / 2
        period_mm = period_fraction * wavelength_mm
        
        # Patch size: typically 60-90% of period
        # Use 75% for nominal design
        patch_fraction = 0.75
        patch_size_mm = patch_fraction * period_mm
        
        # Gap: remaining space
        gap_mm = period_mm - patch_size_mm
        
        uc = UnitCellProperties(
            period_mm=period_mm,
            patch_size_mm=patch_size_mm,
            gap_mm=gap_mm,
        )
        
        if not uc.validate():
            raise ValueError(f"Invalid unit cell calculated: {uc}")
        
        return uc
    
    def build_array(
        self,
        unit_cell: UnitCellProperties,
        target_frequency_ghz: float,
        substrate_height_mm: float,
        epsilon_r: float,
        min_array_dimension_mm: Optional[float] = None,
        target_rows: Optional[int] = None,
        target_cols: Optional[int] = None,
    ) -> AMCArrayDimensions:
        """Build AMC array from unit cell
        
        Array size must satisfy: dimension >= 3 × patch_size
        Typical: 5x5 to 10x10 arrays
        
        Args:
            unit_cell: Unit cell properties
            target_frequency_ghz: Design frequency
            substrate_height_mm: Substrate thickness
            epsilon_r: Relative permittivity
            min_array_dimension_mm: Minimum array physical size (or use default)
            target_rows: Override rows (use default if None)
            target_cols: Override cols (use default if None)
            
        Returns:
            AMCArrayDimensions with array parameters
            
        Raises:
            ValueError: If array is too small
        """
        if not unit_cell.validate():
            raise ValueError(f"Invalid unit cell: {unit_cell}")
        
        # Default array size: 7x7 for good coverage
        default_array_size = 7
        rows = target_rows or default_array_size
        cols = target_cols or default_array_size
        
        # Enforce minimum rule: array physical dimension >= 3 × patch size
        min_dimension_mm = min_array_dimension_mm or (3.5 * unit_cell.patch_size_mm)
        
        min_cells_needed = math.ceil(min_dimension_mm / unit_cell.period_mm)
        if rows < min_cells_needed or cols < min_cells_needed:
            rows = max(rows, min_cells_needed, self.min_array_size)
            cols = max(cols, min_cells_needed, self.min_array_size)
        
        return AMCArrayDimensions(
            rows=rows,
            cols=cols,
            period_mm=unit_cell.period_mm,
            patch_size_mm=unit_cell.patch_size_mm,
            gap_mm=unit_cell.gap_mm,
            substrate_height_mm=substrate_height_mm,
            epsilon_r=epsilon_r,
        )
    
    def calculate_air_gap_distance(
        self,
        target_frequency_ghz: float,
        gap_type: str = "nominal",
    ) -> float:
        """Calculate optimal air gap between patch antenna and AMC
        
        Critical parameter for coupling and frequency matching
        
        Args:
            target_frequency_ghz: Design frequency
            gap_type: "minimal" (2%), "nominal" (5%), "maximal" (8%)
            
        Returns:
            Recommended air gap in mm
            
        Raises:
            ValueError: If gap_type invalid
        """
        wavelength_mm = (self.C_MM_PER_NS * 1000) / target_frequency_ghz
        
        gap_fractions = {
            "minimal": 0.02,
            "nominal": 0.05,
            "maximal": 0.08,
        }
        
        if gap_type not in gap_fractions:
            raise ValueError(f"Invalid gap_type: {gap_type}. Must be one of {list(gap_fractions.keys())}")
        
        fraction = gap_fractions[gap_type]
        gap_mm = fraction * wavelength_mm
        
        return max(0.5, gap_mm)  # Enforce minimum 0.5mm
    
    def predict_performance(
        self,
        unit_cell: UnitCellProperties,
        array: AMCArrayDimensions,
        target_frequency_ghz: float,
        patch_frequency_ghz: float,
    ) -> AMCPerformance:
        """Predict AMC performance
        
        Args:
            unit_cell: Unit cell properties
            array: Array dimensions
            target_frequency_ghz: Design frequency for AMC
            patch_frequency_ghz: Patch antenna operating frequency
            
        Returns:
            Predicted AMC performance
        """
        # Unit cell resonance (simplified LC model)
        # Lower frequency with larger patches/smaller gaps
        resonant_frequency_ghz = target_frequency_ghz
        
        # Reflection phase (should be ~0 at resonance)
        # Simplified: use frequency error to estimate phase deviation
        freq_error_ghz = resonant_frequency_ghz - patch_frequency_ghz
        phase_deviation_deg_per_ghz = 180.0  # Empirical
        reflection_phase_deg = freq_error_ghz * phase_deviation_deg_per_ghz
        reflection_phase_deg = max(-90, min(90, reflection_phase_deg))
        
        # Phase bandwidth (range where phase is ±90 degrees)
        # Typically 2-5% of center frequency
        phase_bandwidth_deg = 180.0  # Full range
        phase_bandwidth_percent = 0.04 * 100  # 4% bandwidth
        
        # Gain improvement from AMC (reduces losses and improves radiation)
        if abs(reflection_phase_deg) < 15:  # Good matching
            gain_improvement_db = 2.5
        elif abs(reflection_phase_deg) < 30:
            gain_improvement_db = 1.5
        else:
            gain_improvement_db = 0.5
        
        # Back lobe reduction (suppresses radiation toward AMC/ground)
        back_lobe_reduction_db = 1.5 + gain_improvement_db * 0.5
        
        # Array efficiency (full metal surface, no ohmic losses in perfect conductor)
        array_efficiency_pct = 95.0
        
        return AMCPerformance(
            resonant_frequency_ghz=resonant_frequency_ghz,
            reflection_phase_deg=reflection_phase_deg,
            phase_bandwidth_deg=phase_bandwidth_deg,
            gain_improvement_db=gain_improvement_db,
            back_lobe_reduction_db=back_lobe_reduction_db,
            array_efficiency_pct=array_efficiency_pct,
        )
    
    def tune_for_frequency(
        self,
        unit_cell: UnitCellProperties,
        current_frequency_ghz: float,
        target_frequency_ghz: float,
    ) -> UnitCellProperties:
        """Tune AMC unit cell to shift resonance
        
        Args:
            unit_cell: Current unit cell
            current_frequency_ghz: Current resonant frequency
            target_frequency_ghz: Desired resonant frequency
            
        Returns:
            Adjusted unit cell
            
        Raises:
            ValueError: If frequency shift too large
        """
        freq_ratio = target_frequency_ghz / current_frequency_ghz
        
        if freq_ratio < 0.8 or freq_ratio > 1.2:
            raise ValueError(
                f"Frequency shift too large: {current_frequency_ghz}→{target_frequency_ghz} GHz"
            )
        
        # Scale wavelength-dependent dimensions
        # Period scales with wavelength (inverse with frequency)
        # For higher frequency, need smaller period
        scaling_factor = 1.0 / freq_ratio
        
        tuned = UnitCellProperties(
            period_mm=unit_cell.period_mm * scaling_factor,
            patch_size_mm=unit_cell.patch_size_mm * scaling_factor,
            gap_mm=unit_cell.gap_mm * scaling_factor,
        )
        
        if not tuned.validate():
            raise ValueError(f"Tuning produced invalid cell: {tuned}")
        
        return tuned
    
    def calculate_alignment_sensitivity(
        self,
        array: AMCArrayDimensions,
    ) -> Dict[str, float]:
        """Calculate sensitivity to misalignment between patch and AMC
        
        Returns:
            Dictionary of alignment parameters and their sensitivities
        """
        array_length_mm, array_width_mm = array.get_array_dimensions_mm()
        
        return {
            "center_offset_tolerance_mm": array.patch_size_mm * 0.2,  # ±20% of patch size
            "rotation_tolerance_deg": 15.0,  # ±15 degrees
            "frequency_sensitivity_mhz_per_mm_gap": 10.0,  # Approximate
        }
