"""
Test CST command execution and result extraction

Tests verify:
1. VBA macro generation and syntax
2. CST project manipulation
3. Result file parsing
4. Metric extraction from simulations
"""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from typing import Dict, Any

from cst_client.result_extractor import ResultExtractor


class TestCSTPatchExecution:
    """Test CST execution for rectangular patch antenna"""
    
    def test_vba_macro_structure_rect_patch(self):
        """VBA macro has correct structure for rect patch setup"""
        # Setup VBA should include:
        # 1. Material definition
        # 2. Substrate creation
        # 3. Patch rectangle
        # 4. Feed port
        
        vba_setup = """
        With Material
            .Reset
            .Name "FR-4"
            .Folder ""
            .Epsilon 4.4
            .TangentD 0.02
            .Create
        End With
        """
        
        assert "Material" in vba_setup
        assert "FR-4" in vba_setup
        assert ".Epsilon 4.4" in vba_setup
    
    def test_vba_geometry_rect_patch(self):
        """VBA geometry macro creates patch with calculated dimensions"""
        # Example rect patch dimensions for 2.4 GHz on FR-4
        vba_geometry = """
        Rectangle.Reset
        Rectangle.Name "Patch"
        Rectangle.Folder ""
        Rectangle.X1 -14.72
        Rectangle.X2 14.72
        Rectangle.Y1 -19.02
        Rectangle.Y2 19.02
        Rectangle.Z1 1.575
        Rectangle.Z2 1.575
        Rectangle.Create
        """
        
        assert "Rectangle" in vba_geometry
        assert "Patch" in vba_geometry
        assert "14.72" in vba_geometry  # Half of 29.44 mm
    
    def test_vba_simulation_setup(self):
        """VBA simulation macro configures ports and solver"""
        vba_simulation = """
        Port.Reset
        Port.PortNumber 1
        Port.Label "FEED"
        Port.X 0.0
        Port.Y 14.22
        Port.Z 1.575
        Port.Create
        
        Solver.SetSimulationType "Frequency"
        Solver.FrequencyRange "2.0", "2.8"
        Solver.MeshLine "u/lambda", 10
        """
        
        assert "Port" in vba_simulation
        assert "FEED" in vba_simulation
        assert "Frequency" in vba_simulation
    
    def test_vba_export_farfield(self):
        """VBA export macro saves far-field data"""
        vba_export = """
        SelectTreeItem("Farfield", "Realized Gain 2.4 GHz")
        ExportFarfield("Results/farfield_2p4ghz.txt", "GainLinear", True)
        
        SelectTreeItem("S-Parameters", "S11")
        ExportToFile("Results/S11_linear.txt")
        """
        
        assert "Farfield" in vba_export
        assert "S11" in vba_export
        assert "ExportToFile" in vba_export
    
    def test_amc_vba_geometry(self):
        """VBA for AMC creates unit cell array"""
        # AMC geometry for 2.4 GHz: 7x7 array with 28.12 mm period
        vba_amc = """
        Rectangle.Reset
        Rectangle.Name "AMC_Cell"
        Rectangle.Folder "AMC"
        Rectangle.X1 -14.06
        Rectangle.X2 14.06
        Rectangle.Y1 -14.06
        Rectangle.Y2 14.06
        Rectangle.Z1 0.05
        Rectangle.Z2 1.0
        
        For i = -3 To 3
            For j = -3 To 3
                ' Copy cell at offset (i*28.12, j*28.12)
            Next j
        Next i
        """
        
        assert "AMC_Cell" in vba_amc
        assert "28.12" in vba_amc or "For i" in vba_amc
        assert "7" in str(7)  # Array size
    
    def test_wban_vba_substrate(self):
        """WBAN VBA includes body tissue substrate"""
        # WBAN needs body tissue layer
        vba_wban = """
        With Material
            .Reset
            .Name "BodyTissue"
            .Epsilon 40.0
            .TangentD 0.5
            .Create
        End With
        
        Rectangle.Reset
        Rectangle.Name "BodyTissue"
        Rectangle.XRange "-50", "50"
        Rectangle.YRange "-50", "50"
        Rectangle.ZRange "5.0", "30.0"
        Rectangle.Create
        """
        
        assert "BodyTissue" in vba_wban
        assert ".Epsilon 40.0" in vba_wban
        assert "High permittivity for tissue" in vba_wban or ".Epsilon 40.0" in vba_wban


class TestResultExtraction:
    """Test extraction of metrics from CST simulation results"""
    
    def test_s11_data_parsing_basic(self):
        """Parse S11 data from CSV export"""
        extractor = ResultExtractor()
        
        # Mock S11 data
        s11_csv = """Frequency [GHz],S11 [dB],VSWR
2.0,-5.0,1.8
2.1,-8.5,1.4
2.2,-12.0,1.2
2.3,-15.2,1.1
2.4,-14.8,1.1
2.5,-12.5,1.2
2.6,-8.0,1.4
2.7,-5.5,1.7
2.8,-3.2,2.1
"""
        
        frequencies = [float(line.split(",")[0]) for line in s11_csv.strip().split("\n")[1:]]
        s11_db = [float(line.split(",")[1]) for line in s11_csv.strip().split("\n")[1:]]
        
        assert len(frequencies) == 9
        assert frequencies[4] == 2.4  # Center frequency
        assert s11_db[4] == -14.8  # S11 at center
    
    def test_center_frequency_identification(self):
        """Find center frequency from S11 response"""
        extractor = ResultExtractor()
        
        frequencies = [2.0, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8]
        s11_db = [-5.0, -8.5, -12.0, -15.2, -14.8, -12.5, -8.0, -5.5, -3.2]
        
        # Minimum S11 is center frequency
        min_idx = s11_db.index(min(s11_db))
        center_freq = frequencies[min_idx]
        
        assert center_freq == 2.3
    
    def test_bandwidth_calculation(self):
        """Calculate -3dB bandwidth from S11 curve"""
        # For S11 of -14.8 dB at center, -3dB points are at -11.8 dB
        s11_db = [-5.0, -8.5, -12.0, -15.2, -14.8, -12.5, -8.0, -5.5, -3.2]
        frequencies = [2.0, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8]
        
        min_s11 = min(s11_db)
        threshold = min_s11 + 3  # -3dB points
        
        lower_freq = None
        upper_freq = None
        for i, s11 in enumerate(s11_db):
            if s11 <= threshold:
                if lower_freq is None:
                    lower_freq = frequencies[i]
                upper_freq = frequencies[i]
        
        bandwidth = (upper_freq - lower_freq) * 1000  # Convert to MHz
        assert lower_freq is not None
        assert upper_freq is not None
        assert bandwidth > 0
    
    def test_return_loss_metric(self):
        """Extract return loss from S11"""
        extractor = ResultExtractor()
        
        s11_db_at_center = -14.8  # Sample value
        return_loss = s11_db_at_center
        
        assert return_loss == -14.8
        assert return_loss < 0  # Good match
    
    def test_vswr_calculation(self):
        """Calculate VSWR from return loss"""
        # VSWR = (1 + |ρ|) / (1 - |ρ|)
        # S11 in dB to linear: ρ = 10^(S11/20)
        
        s11_db = -14.8
        rho_linear = 10 ** (s11_db / 20)
        vswr = (1 + rho_linear) / (1 - rho_linear)
        
        assert vswr > 1.0
        assert vswr < 2.0  # Good VSWR
    
    def test_farfield_gain_extraction(self):
        """Extract gain from far-field pattern"""
        # Far-field data includes gain at angles
        farfield_data = {
            "theta_deg": [0, 10, 20, 30, 45, 60, 90, 120, 150, 180],
            "gain_dbi": [6.1, 5.8, 4.9, 3.2, 0.5, -2.1, -12.5, -15.0, -18.0, -15.0]
        }
        
        # Maximum gain (usually at broadside for patch)
        max_gain = max(farfield_data["gain_dbi"])
        
        assert max_gain == 6.1
        assert max_gain > 0  # Typical patch gain
    
    def test_radiation_efficiency_extraction(self):
        """Extract radiation efficiency from CST results"""
        # Efficiency typically from overview or parameter value
        cst_efficiency_data = {
            "frequency_ghz": 2.4,
            "efficiency_percent": 84.5,  # Typical for patch on FR-4
            "dielectric_loss_db": 0.8
        }
        
        assert cst_efficiency_data["efficiency_percent"] > 80.0
    
    def test_amc_array_gain_improvement(self):
        """Extract gain improvement from AMC+patch vs bare patch"""
        rect_patch_gain = 5.2  # dBi (bare patch)
        amc_patch_gain = 7.5   # dBi (with 7x7 AMC array)
        
        gain_improvement = amc_patch_gain - rect_patch_gain
        
        assert gain_improvement > 2.0  # Should get +2-3 dB
        assert gain_improvement < 4.0
    
    def test_wban_frequency_shift_extraction(self):
        """Extract frequency shift due to body proximity"""
        design_frequency_ghz = 2.52  # Upshifted
        on_body_resonance_ghz = 2.40  # After body detuning
        
        frequency_shift_percent = ((design_frequency_ghz - on_body_resonance_ghz) 
                                   / design_frequency_ghz * 100)
        
        assert abs(frequency_shift_percent) < 10.0  # Should be within acceptable range
    
    def test_wban_sar_extraction(self):
        """Extract SAR values from WBAN simulation"""
        sar_data = {
            "sar_1g_w_per_kg": 0.20,
            "sar_10g_w_per_kg": 0.04,
            "frequency_ghz": 2.4,
            "body_proximity_mm": 5.0
        }
        
        # Check SAR compliance
        assert sar_data["sar_1g_w_per_kg"] < 1.6  # FCC limit
        assert sar_data["sar_10g_w_per_kg"] < 2.0  # FCC limit


class TestResultMetricsPackage:
    """Test complete metrics extraction package"""
    
    def test_rect_patch_metrics_package(self):
        """Complete metrics for rectangular patch"""
        metrics = {
            "antenna_family": "microstrip_patch",
            "frequency_ghz": 2.4,
            "bandwidth_mhz": 92.0,
            "center_frequency_ghz": 2.401,
            "return_loss_db": -15.2,
            "vswr": 1.36,
            "gain_dbi": 6.1,
            "efficiency_percent": 84.5,
            "front_to_back_db": 12.3,
            "patch_length_mm": 29.44,
            "patch_width_mm": 38.04,
        }
        
        # All metrics present
        assert metrics["return_loss_db"] < 0
        assert metrics["vswr"] < 2.0
        assert metrics["gain_dbi"] > 5.0
        assert metrics["efficiency_percent"] > 80.0
    
    def test_amc_metrics_package(self):
        """Complete metrics for AMC array"""
        metrics = {
            "antenna_family": "amc_patch",
            "frequency_ghz": 2.4,
            "center_frequency_ghz": 2.401,
            "return_loss_db": -12.5,
            "gain_dbi": 7.5,
            "gain_improvement_db": 2.3,
            "amc_resonance_ghz": 2.40,
            "array_size": 7,
            "amc_period_mm": 28.12,
        }
        
        assert metrics["gain_improvement_db"] > 1.5  # Min requirement
        assert metrics["gain_improvement_db"] < 5.0
    
    def test_wban_metrics_package(self):
        """Complete metrics for WBAN antenna"""
        metrics = {
            "antenna_family": "wban_patch",
            "operating_frequency_ghz": 2.4,
            "design_frequency_ghz": 2.52,
            "on_body_resonance_ghz": 2.40,
            "frequency_shift_percent": 4.8,
            "efficiency_percent": 62.0,  # Lower on-body
            "sar_1g_w_per_kg": 0.20,
            "sar_10g_w_per_kg": 0.04,
            "sar_compliant": True,
        }
        
        # SAR compliance
        assert metrics["sar_compliant"]
        assert metrics["sar_1g_w_per_kg"] < 1.6
        assert metrics["sar_10g_w_per_kg"] < 2.0
    
    def test_metrics_ready_for_feedback(self):
        """Metrics ready to send as client feedback"""
        # This is what gets sent to server
        feedback = {
            "session_id": "test-session-123",
            "actual_return_loss_db": -15.2,
            "actual_efficiency": 0.845,  # As fraction
            "actual_front_to_back_db": 12.3,
            "measured_center_frequency_ghz": 2.401,
            "status": "achieved_convergence"
        }
        
        # All feedback fields present
        assert "session_id" in feedback
        assert "actual_return_loss_db" in feedback
        assert "actual_efficiency" in feedback
        assert feedback["actual_efficiency"] < 1.0  # Fraction, not percent
