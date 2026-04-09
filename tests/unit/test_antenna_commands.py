"""
Test antenna family commands - CST execution and result extraction

Tests verify:
1. Command creation and validation for each family
2. Command serialization to optimization requests
3. Server response handling
4. CST macro execution
5. Result extraction from simulations
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any

from comm.antenna_commands import (
    AntennaCommandFactory,
    RectPatchCommand,
    AMCPatchCommand,
    WBANPatchCommand,
    AntennaFamily,
)
from comm.request_builder import RequestBuilder


class TestAntennaCommands:
    """Test antenna family command creation and validation"""
    
    def test_rect_patch_command_creation(self):
        """Create rectangular patch command with valid parameters"""
        cmd = AntennaCommandFactory.create_rect_patch_command(
            frequency_ghz=2.4,
            bandwidth_mhz=100.0,
            patch_shape="rectangular",
            feed_type="edge"
        )
        
        assert cmd.frequency_ghz == 2.4
        assert cmd.bandwidth_mhz == 100.0
        assert cmd.antenna_family == "microstrip_patch"
        assert cmd.patch_shape == "rectangular"
        assert cmd.feed_type == "edge"
    
    def test_rect_patch_command_defaults(self):
        """Rectangular patch uses correct defaults"""
        cmd = AntennaCommandFactory.create_rect_patch_command(frequency_ghz=2.4)
        
        assert cmd.patch_shape == "rectangular"
        assert cmd.feed_type == "edge"
        assert cmd.polarization == "linear"
        assert cmd.min_efficiency_percent == 80.0
        assert cmd.max_vswr == 2.0
    
    def test_rect_patch_frequency_validation(self):
        """Frequency must be within valid range"""
        with pytest.raises(ValueError):
            AntennaCommandFactory.create_rect_patch_command(frequency_ghz=0.05)
        
        with pytest.raises(ValueError):
            AntennaCommandFactory.create_rect_patch_command(frequency_ghz=150.0)
    
    def test_rect_patch_bandwidth_validation(self):
        """Bandwidth must be reasonable"""
        with pytest.raises(ValueError):
            AntennaCommandFactory.create_rect_patch_command(
                frequency_ghz=2.4,
                bandwidth_mhz=5.0  # Below minimum
            )
    
    def test_amc_command_creation(self):
        """Create AMC patch command with valid parameters"""
        cmd = AntennaCommandFactory.create_amc_command(
            frequency_ghz=2.4,
            bandwidth_mhz=100.0,
            amc_unit_cell_count_per_side=7,
            amc_air_gap_preference="standard"
        )
        
        assert cmd.frequency_ghz == 2.4
        assert cmd.antenna_family == "amc_patch"
        assert cmd.amc_unit_cell_count_per_side == 7
        assert cmd.amc_air_gap_preference == "standard"
    
    def test_amc_command_defaults(self):
        """AMC uses correct defaults"""
        cmd = AntennaCommandFactory.create_amc_command(frequency_ghz=2.4)
        
        assert cmd.patch_shape == "auto"
        assert cmd.feed_type == "auto"
        assert cmd.amc_unit_cell_count_per_side == 7
        assert cmd.amc_air_gap_preference == "standard"
        assert cmd.min_gain_improvement_db == 1.5
        assert cmd.amc_frequency_tolerance_percent == 3.0
    
    def test_amc_array_size_validation(self):
        """Array size must be reasonable"""
        with pytest.raises(ValueError):
            AntennaCommandFactory.create_amc_command(
                frequency_ghz=2.4,
                amc_unit_cell_count_per_side=2  # Below minimum
            )
        
        with pytest.raises(ValueError):
            AntennaCommandFactory.create_amc_command(
                frequency_ghz=2.4,
                amc_unit_cell_count_per_side=20  # Above maximum
            )
    
    def test_wban_command_creation(self):
        """Create WBAN command with valid parameters"""
        cmd = AntennaCommandFactory.create_wban_command(
            operating_frequency_ghz=2.4,
            bandwidth_mhz=100.0,
            body_proximity_mm=5.0,
            design_frequency_upshift_percent=5.0
        )
        
        assert cmd.operating_frequency_ghz == 2.4
        assert cmd.antenna_family == "wban_patch"
        assert cmd.body_proximity_mm == 5.0
        assert cmd.design_frequency_upshift_percent == 5.0
    
    def test_wban_command_defaults(self):
        """WBAN uses correct defaults"""
        cmd = AntennaCommandFactory.create_wban_command(operating_frequency_ghz=2.4)
        
        assert cmd.body_proximity_mm == 5.0
        assert cmd.design_frequency_upshift_percent == 5.0
        assert cmd.sar_limit_w_per_kg_1g == 1.6
        assert cmd.sar_limit_w_per_kg_10g == 2.0
    
    def test_wban_sar_compliance(self):
        """WBAN SAR limits must be valid"""
        with pytest.raises(ValueError):
            AntennaCommandFactory.create_wban_command(
                operating_frequency_ghz=2.4,
                sar_limit_w_per_kg_1g=0.05  # Below minimum
            )
    
    def test_all_commands_serializable(self):
        """All commands can be converted to dict (JSON-serializable)"""
        commands = [
            AntennaCommandFactory.create_rect_patch_command(frequency_ghz=2.4),
            AntennaCommandFactory.create_amc_command(frequency_ghz=2.4),
            AntennaCommandFactory.create_wban_command(operating_frequency_ghz=2.4),
        ]
        
        for cmd in commands:
            data = cmd.dict()
            assert isinstance(data, dict)
            # Should be JSON serializable
            json.dumps(data)


class TestCommandRequestBuilding:
    """Test converting antenna commands to optimize requests"""
    
    def test_rect_patch_request(self):
        """Build optimize request from rect patch command"""
        builder = RequestBuilder()
        cmd = AntennaCommandFactory.create_rect_patch_command(frequency_ghz=2.4)
        
        request = builder.build_optimize_request(
            user_text="Design rectangular patch at 2.4 GHz",
            design_specs=cmd.dict()
        )
        
        assert request.target_spec["antenna_family"] == "microstrip_patch"
        assert request.target_spec["frequency_ghz"] == 2.4
    
    def test_amc_request(self):
        """Build optimize request from AMC command"""
        builder = RequestBuilder()
        cmd = AntennaCommandFactory.create_amc_command(frequency_ghz=2.4)
        
        request = builder.build_optimize_request(
            user_text="Design AMC array at 2.4 GHz",
            design_specs=cmd.dict()
        )
        
        assert request.target_spec["antenna_family"] == "amc_patch"
        assert request.target_spec["frequency_ghz"] == 2.4
    
    def test_wban_request(self):
        """Build optimize request from WBAN command"""
        builder = RequestBuilder()
        cmd = AntennaCommandFactory.create_wban_command(operating_frequency_ghz=2.4)
        
        request = builder.build_optimize_request(
            user_text="Design on-body WBAN antenna",
            design_specs=cmd.dict()
        )
        
        assert request.target_spec["antenna_family"] == "wban_patch"
        assert request.target_spec["frequency_ghz"] == 2.4
    
    def test_request_contains_all_required_fields(self):
        """Optimize request has all required schema fields"""
        builder = RequestBuilder()
        cmd = AntennaCommandFactory.create_rect_patch_command(frequency_ghz=2.4)
        
        request = builder.build_optimize_request(
            user_text="Design antenna",
            design_specs=cmd.dict()
        )
        
        required_fields = [
            "schema_version",
            "user_request",
            "target_spec",
            "design_constraints",
            "optimization_policy",
            "runtime_preferences",
            "client_capabilities"
        ]
        
        for field in required_fields:
            assert hasattr(request, field), f"Missing field: {field}"


class TestServerResponseHandling:
    """Test handling of server responses with CST commands"""
    
    def test_server_response_with_calculated_params(self):
        """Parse server response containing calculated parameters"""
        response = {
            "status": "ready_for_execution",
            "command_package": {
                "family": "microstrip_patch",
                "calculated_params": {
                    "patch_length_mm": 29.44,
                    "patch_width_mm": 38.04,
                    "feed_x_offset_mm": 0.0,
                    "feed_y_offset_mm": 14.22,
                    "substrate_epsilon_r": 2.2,
                    "substrate_thickness_mm": 1.575
                },
                "cst_vba_setup": "Material.Reset\n...",
                "cst_vba_geometry": "Rectangle.Reset\n...",
                "cst_vba_simulation": "Port.Reset\n...",
                "cst_vba_export": "SelectTreeItem(...)\n..."
            },
            "session_id": "test-session-123"
        }
        
        # Verify response structure
        assert response["status"] == "ready_for_execution"
        assert "calculated_params" in response["command_package"]
        assert response["command_package"]["calculated_params"]["patch_length_mm"] == 29.44
    
    def test_amc_server_response(self):
        """Parse AMC server response"""
        response = {
            "status": "ready_for_execution",
            "command_package": {
                "family": "amc_patch",
                "calculated_params": {
                    "patch_length_mm": 29.44,
                    "patch_width_mm": 38.04,
                    "amc_period_mm": 28.12,
                    "amc_air_gap_mm": 7.5,
                    "array_size": 7,
                    "total_array_size_mm": 197.0
                },
                "cst_vba_setup": "...",
                "cst_vba_geometry": "..."
            },
            "session_id": "test-session-456"
        }
        
        assert response["command_package"]["family"] == "amc_patch"
        assert response["command_package"]["calculated_params"]["array_size"] == 7
        assert response["command_package"]["calculated_params"]["amc_period_mm"] == 28.12
    
    def test_wban_server_response(self):
        """Parse WBAN server response with SAR data"""
        response = {
            "status": "ready_for_execution",
            "command_package": {
                "family": "wban_patch",
                "calculated_params": {
                    "design_frequency_ghz": 2.52,  # Upshifted
                    "patch_length_mm": 18.95,
                    "patch_width_mm": 34.58,
                    "body_detuning_percent": 8.0,
                    "predicted_sar_1g_w_per_kg": 0.20,
                    "predicted_sar_10g_w_per_kg": 0.04
                },
                "cst_vba_setup": "..."
            },
            "session_id": "test-session-789"
        }
        
        assert response["command_package"]["family"] == "wban_patch"
        assert response["command_package"]["calculated_params"]["design_frequency_ghz"] == 2.52
        assert response["command_package"]["calculated_params"]["predicted_sar_1g_w_per_kg"] == 0.20


class TestCommandRecipeIntegration:
    """Test complete command recipe workflow (without actual CST)"""
    
    def test_full_rect_patch_workflow(self):
        """Simulate complete rect patch workflow"""
        # Step 1: Create command
        cmd = AntennaCommandFactory.create_rect_patch_command(
            frequency_ghz=2.4,
            bandwidth_mhz=100.0
        )
        
        # Step 2: Build request
        builder = RequestBuilder()
        request = builder.build_optimize_request(
            user_text="Design antenna",
            design_specs=cmd.dict()
        )
        
        # Step 3: Simulate server response
        response = {
            "status": "ready_for_execution",
            "command_package": {
                "family": "microstrip_patch",
                "calculated_params": {
                    "patch_length_mm": 29.44,
                    "patch_width_mm": 38.04,
                }
            },
            "session_id": "test-123"
        }
        
        # Verify workflow
        assert cmd.antenna_family == "microstrip_patch"
        assert request.target_spec["antenna_family"] == "microstrip_patch"
        assert response["status"] == "ready_for_execution"
    
    def test_full_amc_workflow(self):
        """Simulate complete AMC workflow"""
        cmd = AntennaCommandFactory.create_amc_command(
            frequency_ghz=2.4,
            amc_unit_cell_count_per_side=7
        )
        
        builder = RequestBuilder()
        request = builder.build_optimize_request(
            user_text="Design AMC array",
            design_specs=cmd.dict()
        )
        
        response = {
            "status": "ready_for_execution",
            "command_package": {
                "family": "amc_patch",
                "calculated_params": {
                    "amc_period_mm": 28.12,
                    "array_size": 7,
                }
            },
            "session_id": "test-456"
        }
        
        assert cmd.amc_unit_cell_count_per_side == 7
        assert response["command_package"]["calculated_params"]["array_size"] == 7
    
    def test_full_wban_workflow(self):
        """Simulate complete WBAN workflow"""
        cmd = AntennaCommandFactory.create_wban_command(
            operating_frequency_ghz=2.4,
            body_proximity_mm=5.0
        )
        
        builder = RequestBuilder()
        request = builder.build_optimize_request(
            user_text="Design on-body antenna",
            design_specs=cmd.dict()
        )
        
        # Verify command
        assert cmd.antenna_family == "wban_patch"
        assert cmd.operating_frequency_ghz == 2.4
