"""Comprehensive tests for antenna calculation modules

Tests all three antenna family calculators:
- RectangularPatchCalculator
- AMCCalculator
- WBANCalculator

Coverage includes:
- Basic parameter calculation
- Validation and error handling
- Physical constraint enforcement
- Performance prediction
- Integration scenarios
"""

import pytest
import math
from src.tools.antenna_calculations.rect_patch_calculator import (
    RectangularPatchCalculator,
    SubstrateProperties,
    RectPatchDimensions,
    RectPatchPerformance,
)
from src.tools.antenna_calculations.amc_calculator import (
    AMCCalculator,
    UnitCellProperties,
    AMCArrayDimensions,
    AMCPerformance,
)
from src.tools.antenna_calculations.wban_calculator import (
    WBANCalculator,
    BodyProperties,
    WBANDesignParameters,
    WBANPerformance,
)


# ============================================================================
# RECTANGULAR PATCH TESTS
# ============================================================================

class TestRectangularPatchCalculator:
    """Test rectangular patch antenna calculations"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.calc = RectangularPatchCalculator()
        self.substrate_fr4 = SubstrateProperties(
            epsilon_r=4.4,
            height_mm=1.6,
            tan_delta=0.019,
        )
        self.substrate_rogers = SubstrateProperties(
            epsilon_r=2.2,
            height_mm=0.254,
            tan_delta=0.0009,
        )
    
    def test_substrate_validation(self):
        """Test substrate property validation"""
        valid = SubstrateProperties(epsilon_r=4.4, height_mm=1.6)
        assert valid.validate()
        
        invalid_er = SubstrateProperties(epsilon_r=0.5, height_mm=1.6)
        assert not invalid_er.validate()
        
        invalid_h = SubstrateProperties(epsilon_r=4.4, height_mm=15.0)
        assert not invalid_h.validate()
    
    def test_calculate_dimensions_2_4_ghz(self):
        """Test dimension calculation at 2.4 GHz"""
        dims = self.calc.calculate_dimensions(
            target_frequency_ghz=2.4,
            substrate=self.substrate_fr4,
            target_bandwidth_mhz=100.0,
        )
        
        assert dims.validate()
        assert dims.length_mm > 0
        assert dims.width_mm > 0
        # Both dimensions should be reasonable
        assert 10 < dims.length_mm < 100  # Realistic microstrip patch 
        assert 10 < dims.width_mm < 150
        assert dims.feed_width_mm > 0
        assert dims.feed_offset_y_mm > 0
        assert dims.feed_offset_y_mm < dims.length_mm
    
    def test_calculate_dimensions_5_ghz(self):
        """Test dimension calculation at 5 GHz"""
        dims = self.calc.calculate_dimensions(
            target_frequency_ghz=5.0,
            substrate=self.substrate_fr4,
        )
        
        assert dims.validate()
        # Higher frequency should give smaller dimensions
        dims_low_freq = self.calc.calculate_dimensions(
            target_frequency_ghz=2.4,
            substrate=self.substrate_fr4,
        )
        assert dims.length_mm < dims_low_freq.length_mm
    
    def test_calculate_dimensions_low_loss_substrate(self):
        """Test with low-loss Rogers substrate"""
        dims = self.calc.calculate_dimensions(
            target_frequency_ghz=2.4,
            substrate=self.substrate_rogers,
        )
        
        assert dims.validate()
        # Lower epsilon means larger patch
        dims_fr4 = self.calc.calculate_dimensions(
            target_frequency_ghz=2.4,
            substrate=self.substrate_fr4,
        )
        assert dims.length_mm > dims_fr4.length_mm  # Larger with lower epsilon
    
    def test_predict_performance_reasonable(self):
        """Test performance prediction is physically reasonable"""
        dims = self.calc.calculate_dimensions(
            target_frequency_ghz=2.4,
            substrate=self.substrate_fr4,
        )
        
        perf = self.calc.predict_performance(
            target_frequency_ghz=2.4,
            dimensions=dims,
            substrate=self.substrate_fr4,
        )
        
        # Reasonable performance ranges
        assert 2.0 <= perf.resonant_frequency_ghz <= 3.0
        assert -30 <= perf.return_loss_db <= -6  # Return loss should be negative
        assert 1.0 <= perf.vswr <= 5.0
        assert 0 <= perf.gain_dbi <= 15.0
        assert 0 <= perf.bandwidth_mhz <= 500
        assert 0 <= perf.efficiency_pct <= 100
        
        # Typical return loss (should be at least -6 dB for resonance)
        assert perf.return_loss_db <= -6
        
        # Typical gain
        assert 2 <= perf.gain_dbi <= 9  # Typical patch gain
        
        # High efficiency with low-loss substrate
        assert perf.efficiency_pct > 50
    
    def test_performance_meets_acceptance_criteria(self):
        """Test if calculated performance meets typical acceptance"""
        dims = self.calc.calculate_dimensions(
            target_frequency_ghz=2.4,
            substrate=self.substrate_rogers,
        )
        
        perf = self.calc.predict_performance(
            target_frequency_ghz=2.4,
            dimensions=dims,
            substrate=self.substrate_rogers,
        )
        
        # Should meet basic acceptance criteria
        assert perf.return_loss_db <= -10 or perf.vswr <= 2.0  # At least one acceptable
        assert perf.efficiency_pct > 50
    
    def test_noise_variation(self):
        """Test manufacturing tolerance variation"""
        dims = self.calc.calculate_dimensions(
            target_frequency_ghz=2.4,
            substrate=self.substrate_fr4,
        )
        
        variations = self.calc.calculate_noise_variation(dims, noise_percent=5.0)
        
        assert len(variations) == 4
        assert "length_mm" in variations
        assert "width_mm" in variations
        
        # Each should have (min, max) tuple
        for param, (vmin, vmax) in variations.items():
            assert vmin > 0
            assert vmax > vmin
            # Tolerance should be 5%
            assert abs(vmin - dims.length_mm) / dims.length_mm < 0.06 or param != "length_mm"
    
    def test_dimensions_invalid_frequency(self):
        """Test error handling for invalid frequency"""
        with pytest.raises(ValueError):
            self.calc.calculate_dimensions(
                target_frequency_ghz=-1.0,
                substrate=self.substrate_fr4,
            )
        
        with pytest.raises(ValueError):
            self.calc.calculate_dimensions(
                target_frequency_ghz=0.0,
                substrate=self.substrate_fr4,
            )


# ============================================================================
# AMC TESTS
# ============================================================================

class TestAMCCalculator:
    """Test AMC unit cell and array calculations"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.calc = AMCCalculator()
        self.target_freq = 2.4  # GHz
    
    def test_unit_cell_properties_validation(self):
        """Test unit cell validation"""
        valid = UnitCellProperties(
            period_mm=50.0,
            patch_size_mm=37.0,
            gap_mm=13.0,
        )
        assert valid.validate()
        
        invalid_gap = UnitCellProperties(
            period_mm=50.0,
            patch_size_mm=45.0,
            gap_mm=10.0,  # Sum exceeds period
        )
        assert not invalid_gap.validate()
    
    def test_calculate_unit_cell_2_4_ghz(self):
        """Test unit cell calculation at 2.4 GHz"""
        uc = self.calc.calculate_unit_cell(
            target_frequency_ghz=2.4,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
        )
        
        assert uc.validate()
        assert uc.period_mm > 0
        assert uc.patch_size_mm > 0
        assert uc.gap_mm > 0
        
        # Period should be reasonable fraction of wavelength (0.15-0.30 lambda)
        wavelength_mm = 300.0 / 2.4  # Correct formula: 300 mm/ns / freq in GHz
        assert 0.1 * wavelength_mm < uc.period_mm < 0.4 * wavelength_mm
        
        # Patch fraction should be reasonable (60-90%)
        patch_fraction = uc.patch_size_mm / uc.period_mm
        assert 0.6 < patch_fraction < 0.9
    
    def test_calculate_unit_cell_5_ghz(self):
        """Test unit cell at higher frequency"""
        uc_2p4 = self.calc.calculate_unit_cell(
            target_frequency_ghz=2.4,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
        )
        
        uc_5 = self.calc.calculate_unit_cell(
            target_frequency_ghz=5.0,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
        )
        
        # Higher frequency should give smaller unit cell
        assert uc_5.period_mm < uc_2p4.period_mm
    
    def test_build_array_minimum_size(self):
        """Test array sizing with minimum constraints"""
        uc = self.calc.calculate_unit_cell(
            target_frequency_ghz=2.4,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
        )
        
        array = self.calc.build_array(
            unit_cell=uc,
            target_frequency_ghz=2.4,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
        )
        
        assert array.validate()
        assert array.rows >= 3
        assert array.cols >= 3
        
        # Array dimensions should be >= 3 × patch size
        length_mm, width_mm = array.get_array_dimensions_mm()
        min_required = 3.0 * uc.patch_size_mm
        assert length_mm >= min_required * 0.95  # Small tolerance
    
    def test_air_gap_distance_nominal(self):
        """Test air gap calculation"""
        gap_min = self.calc.calculate_air_gap_distance(
            target_frequency_ghz=2.4,
            gap_type="minimal",
        )
        
        gap_nom = self.calc.calculate_air_gap_distance(
            target_frequency_ghz=2.4,
            gap_type="nominal",
        )
        
        gap_max = self.calc.calculate_air_gap_distance(
            target_frequency_ghz=2.4,
            gap_type="maximal",
        )
        
        assert gap_min > 0
        assert gap_nom > gap_min
        assert gap_max > gap_nom
    
    def test_air_gap_invalid_type(self):
        """Test error handling for invalid gap type"""
        with pytest.raises(ValueError):
            self.calc.calculate_air_gap_distance(
                target_frequency_ghz=2.4,
                gap_type="invalid",
            )
    
    def test_predict_performance(self):
        """Test AMC performance prediction"""
        uc = self.calc.calculate_unit_cell(
            target_frequency_ghz=2.4,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
        )
        
        array = self.calc.build_array(
            unit_cell=uc,
            target_frequency_ghz=2.4,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
        )
        
        perf = self.calc.predict_performance(
            unit_cell=uc,
            array=array,
            target_frequency_ghz=2.4,
            patch_frequency_ghz=2.4,
        )
        
        # Check reasonable ranges
        assert 2.0 <= perf.resonant_frequency_ghz <= 3.0
        assert -90 <= perf.reflection_phase_deg <= 90
        assert perf.gain_improvement_db > 0
        assert perf.back_lobe_reduction_db > 0
        assert perf.array_efficiency_pct > 90
    
    def test_performance_matching_condition(self):
        """Test AMC-patch frequency matching condition"""
        uc = self.calc.calculate_unit_cell(
            target_frequency_ghz=2.4,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
        )
        
        array = self.calc.build_array(
            unit_cell=uc,
            target_frequency_ghz=2.4,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
        )
        
        perf = self.calc.predict_performance(
            unit_cell=uc,
            array=array,
            target_frequency_ghz=2.4,
            patch_frequency_ghz=2.4,
        )
        
        # Should be matched (same design frequency)
        assert perf.is_matched_to_patch(patch_frequency_ghz=2.4, tolerance_pct=3.0)
    
    def test_tune_for_frequency(self):
        """Test AMC frequency tuning"""
        uc_original = self.calc.calculate_unit_cell(
            target_frequency_ghz=2.4,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
        )
        
        # Tune to 2.5 GHz (small shift)
        uc_tuned = self.calc.tune_for_frequency(
            unit_cell=uc_original,
            current_frequency_ghz=2.4,
            target_frequency_ghz=2.5,
        )
        
        assert uc_tuned.validate()
        # Period should shrink for higher frequency
        assert uc_tuned.period_mm < uc_original.period_mm
    
    def test_tune_excessive_shift(self):
        """Test error for excessive frequency shift"""
        uc = self.calc.calculate_unit_cell(
            target_frequency_ghz=2.4,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
        )
        
        # Try to shift by +50% (should fail)
        with pytest.raises(ValueError):
            self.calc.tune_for_frequency(
                unit_cell=uc,
                current_frequency_ghz=2.4,
                target_frequency_ghz=3.6,
            )


# ============================================================================
# WBAN TESTS
# ============================================================================

class TestWBANCalculator:
    """Test WBAN antenna calculations"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.calc = WBANCalculator()
        self.body_nominal = BodyProperties(
            distance_mm=5.0,
            bending_radius_mm=50.0,
        )
        self.body_far = BodyProperties(
            distance_mm=20.0,
            bending_radius_mm=None,
        )
    
    def test_body_properties_validation(self):
        """Test body property validation"""
        valid = BodyProperties(distance_mm=5.0)
        assert valid.validate()
        
        invalid_dist_near = BodyProperties(distance_mm=1.0)
        assert not invalid_dist_near.validate()
        
        invalid_dist_far = BodyProperties(distance_mm=100.0)
        assert not invalid_dist_far.validate()
    
    def test_calculate_design_frequency_minimal(self):
        """Test design frequency calculation with minimal compensation"""
        design_freq = self.calc.calculate_design_frequency(
            target_frequency_ghz=2.4,
            body_distance_mm=5.0,
            compensation_type="minimal",
        )
        
        # Should be higher than target
        assert design_freq > 2.4
        # Minimal compensation is 3%
        expected_min = 2.4 * 1.03
        assert design_freq >= expected_min * 0.99
    
    def test_calculate_design_frequency_nominal(self):
        """Test design frequency with nominal compensation"""
        design_freq = self.calc.calculate_design_frequency(
            target_frequency_ghz=2.4,
            body_distance_mm=5.0,
            compensation_type="nominal",
        )
        
        assert design_freq > 2.4
        expected = 2.4 * 1.06
        assert abs(design_freq - expected) / expected < 0.1
    
    def test_calculate_design_frequency_distance_dependent(self):
        """Test that design frequency depends on body distance"""
        freq_close = self.calc.calculate_design_frequency(
            target_frequency_ghz=2.4,
            body_distance_mm=3.0,
            compensation_type="nominal",
        )
        
        freq_far = self.calc.calculate_design_frequency(
            target_frequency_ghz=2.4,
            body_distance_mm=25.0,
            compensation_type="nominal",
        )
        
        # Closer body needs more compensation
        assert freq_close > freq_far
    
    def test_calculate_dimensions_with_body(self):
        """Test WBAN dimension calculation"""
        design_freq = self.calc.calculate_design_frequency(
            target_frequency_ghz=2.4,
            body_distance_mm=5.0,
        )
        
        dims = self.calc.calculate_dimensions(
            design_frequency_ghz=design_freq,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
            body_properties=self.body_nominal,
        )
        
        assert dims.validate()
        assert dims.length_mm > 0
        assert dims.width_mm > 0
        assert dims.ground_slot_length_mm > 0
        assert dims.ground_slot_width_mm > 0
    
    def test_predict_on_body_performance(self):
        """Test on-body performance prediction"""
        design_freq = self.calc.calculate_design_frequency(
            target_frequency_ghz=2.4,
            body_distance_mm=5.0,
        )
        
        dims = self.calc.calculate_dimensions(
            design_frequency_ghz=design_freq,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
            body_properties=self.body_nominal,
        )
        
        perf = self.calc.predict_on_body_performance(
            design_frequency_ghz=design_freq,
            target_frequency_ghz=2.4,
            dimensions=dims,
            substrate_epsilon_r=4.4,
            body_properties=self.body_nominal,
            transmitted_power_dbm=0.0,
        )
        
        # Reasonable ranges
        assert perf.resonant_frequency_on_body_ghz > 0
        assert perf.gain_on_body_dbi > 0
        assert 30 <= perf.efficiency_on_body_pct <= 100
        assert perf.frequency_shift_mhz != 0  # Should have detuning
        assert perf.detuning_pct < 10  # Should be less than 10%
        assert perf.sar_1g_w_kg >= 0
        assert perf.sar_10g_w_kg >= 0
        # 1g SAR is from smaller averaging volume, so it's higher or equal to 10g SAR
        assert perf.sar_1g_w_kg >= perf.sar_10g_w_kg * 0.9  # Allow some tolerance
    
    def test_sar_safety_check(self):
        """Test SAR safety validation"""
        perf_safe = WBANPerformance(
            resonant_frequency_free_space_ghz=2.4,
            gain_free_space_dbi=4.0,
            efficiency_free_space_pct=85.0,
            resonant_frequency_on_body_ghz=2.35,
            gain_on_body_dbi=3.0,
            efficiency_on_body_pct=70.0,
            frequency_shift_mhz=50,
            detuning_pct=2.0,
            sar_1g_w_kg=0.5,
            sar_10g_w_kg=0.2,
            return_loss_on_body_db=-15,
            vswr_on_body=1.3,
        )
        
        assert perf_safe.is_safe()
        
        # Unsafe case
        perf_unsafe = WBANPerformance(
            resonant_frequency_free_space_ghz=2.4,
            gain_free_space_dbi=4.0,
            efficiency_free_space_pct=85.0,
            resonant_frequency_on_body_ghz=2.35,
            gain_on_body_dbi=3.0,
            efficiency_on_body_pct=70.0,
            frequency_shift_mhz=50,
            detuning_pct=2.0,
            sar_1g_w_kg=2.5,  # Exceeds limit
            sar_10g_w_kg=2.5,
            return_loss_on_body_db=-15,
            vswr_on_body=1.3,
        )
        
        assert not perf_unsafe.is_safe()
    
    def test_account_for_bending(self):
        """Test bending effect calculation"""
        dims = self.calc.calculate_dimensions(
            design_frequency_ghz=2.45,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
            body_properties=self.body_nominal,
        )
        
        bending_effects = self.calc.account_for_bending(
            dimensions=dims,
            bending_radius_mm=50.0,
        )
        
        assert "compression_factor" in bending_effects
        assert "frequency_shift_pct" in bending_effects
        assert 0 < bending_effects["compression_factor"] < 1
        assert bending_effects["frequency_shift_pct"] > 0
    
    def test_bending_invalid_radius(self):
        """Test error for invalid bending radius"""
        dims = self.calc.calculate_dimensions(
            design_frequency_ghz=2.45,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
            body_properties=self.body_nominal,
        )
        
        # Radius too small
        with pytest.raises(ValueError):
            self.calc.account_for_bending(
                dimensions=dims,
                bending_radius_mm=5.0,  # Too small
            )


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests across multiple calculators"""
    
    def test_rect_patch_with_amc_integration(self):
        """Test rectangular patch + AMC integration scenario"""
        # Design rectangular patch
        rect_calc = RectangularPatchCalculator()
        substrate = SubstrateProperties(epsilon_r=4.4, height_mm=1.6)
        
        patch_dims = rect_calc.calculate_dimensions(
            target_frequency_ghz=2.4,
            substrate=substrate,
        )
        
        patch_perf = rect_calc.predict_performance(
            target_frequency_ghz=2.4,
            dimensions=patch_dims,
            substrate=substrate,
        )
        
        # Design AMC for same frequency
        amc_calc = AMCCalculator()
        amc_uc = amc_calc.calculate_unit_cell(
            target_frequency_ghz=2.4,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
        )
        
        amc_array = amc_calc.build_array(
            unit_cell=amc_uc,
            target_frequency_ghz=2.4,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
        )
        
        amc_perf = amc_calc.predict_performance(
            unit_cell=amc_uc,
            array=amc_array,
            target_frequency_ghz=2.4,
            patch_frequency_ghz=patch_perf.resonant_frequency_ghz,
        )
        
        # AMC should be matched to patch
        assert amc_perf.is_matched_to_patch(
            patch_frequency_ghz=patch_perf.resonant_frequency_ghz,
            tolerance_pct=3.0,
        )
        
        # Air gap between them
        air_gap = amc_calc.calculate_air_gap_distance(
            target_frequency_ghz=2.4,
            gap_type="nominal",
        )
        assert air_gap > 0
    
    def test_wban_patch_design_workflow(self):
        """Test complete WBAN design workflow"""
        target_freq = 2.4
        body = BodyProperties(distance_mm=5.0)
        
        # 1. Calculate design frequency with compensation
        wban_calc = WBANCalculator()
        design_freq = wban_calc.calculate_design_frequency(
            target_frequency_ghz=target_freq,
            body_distance_mm=body.distance_mm,
        )
        
        assert design_freq > target_freq
        
        # 2. Calculate dimensions
        dims = wban_calc.calculate_dimensions(
            design_frequency_ghz=design_freq,
            substrate_height_mm=1.6,
            epsilon_r=4.4,
            body_properties=body,
        )
        
        assert dims.validate()
        
        # 3. Predict on-body performance
        perf = wban_calc.predict_on_body_performance(
            design_frequency_ghz=design_freq,
            target_frequency_ghz=target_freq,
            dimensions=dims,
            substrate_epsilon_r=4.4,
            body_properties=body,
        )
        
        # Should meet safety and performance targets
        assert perf.is_safe()
        assert perf.meets_performance_targets()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
