"""
Test fixtures and utilities for integration testing
"""

import asyncio
import json
from pathlib import Path
import sys
from typing import Dict, Any, Optional
from unittest.mock import Mock, AsyncMock, MagicMock
import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from comm.server_connector import ServerConnector
from comm.api_client import ApiClient
from comm.initializer import ClientInitializer
from session.session_store import SessionStore


class MockServerConnector:
    """Mock server connector for testing without real server"""
    
    def __init__(self):
        self.calls = []
        self.responses = {}
    
    async def get(self, endpoint: str) -> Dict[str, Any]:
        """Mock GET request"""
        self.calls.append(("GET", endpoint))
        
        # Predefined responses
        responses = {
            "/api/v1/health": {
                "status": "ok",
                "service": "AMC Antenna Optimization Server",
                "version": "0.1.0",
                "ann_status": "available",
                "llm_status": "available",
            },
            "/api/v1/capabilities": {
                "capabilities": {
                    "supported_antenna_families": ["amc_patch", "microstrip_patch", "wban_patch"],
                    "frequency_range_ghz": {"min": 0.5, "max": 10.0},
                }
            }
        }
        
        # Handle session endpoints
        if endpoint.startswith("/api/v1/sessions/"):
            session_id = endpoint.split("/")[-1]
            return {
                "session_id": session_id,
                "status": "active",
                "current_iteration": 0,
            }
        
        return responses.get(endpoint, {})
    
    async def post(self, endpoint: str, json: Dict[str, Any]) -> Dict[str, Any]:
        """Mock POST request"""
        self.calls.append(("POST", endpoint, json))
        
        # Predefined responses
        if endpoint == "/api/v1/optimize":
            return {
                "schema_version": "optimize_response.v1",
                "status": "accepted",
                "session_id": "test-session-" + json.get("user_request", "")[:20],
                "trace_id": "trace-test-001",
                "current_stage": "planning_commands",
                "ann_prediction": {
                    "ann_model_version": "v1",
                    "confidence": 0.82,
                    "dimensions": {
                        "patch_length_mm": 30.2,
                        "patch_width_mm": 38.1,
                        "patch_height_mm": 0.035,
                        "substrate_length_mm": 45.0,
                        "substrate_width_mm": 50.0,
                        "substrate_height_mm": 1.6,
                        "feed_length_mm": 12.0,
                        "feed_width_mm": 3.0,
                        "feed_offset_x_mm": 0.0,
                        "feed_offset_y_mm": -6.0,
                    }
                },
                "command_package": {
                    "schema_version": "cst_command_package.v1",
                    "session_id": "test-session-" + json.get("user_request", "")[:20],
                    "trace_id": "trace-test-001",
                    "design_id": "design-test-001",
                    "iteration_index": 0,
                    "commands": [
                        {"seq": 1, "command": "create_project", "params": {"project_name": "test"}},
                        {"seq": 2, "command": "set_units", "params": {"unit": "mm"}},
                        {"seq": 3, "command": "set_frequency_range", "params": {}},
                    ]
                },
                "warnings": []
            }
        
        elif endpoint == "/api/v1/client-feedback":
            return {
                "status": "completed",
                "accepted": True,
                "message": "Design optimization successful"
            }
        
        return {}


@pytest.fixture
def mock_connector():
    """Provide mock server connector"""
    return MockServerConnector()


@pytest.fixture
def session_store():
    """Provide session store"""
    store = SessionStore()
    # Clean up test sessions
    yield store
    # Cleanup
    for session_id in list(store.sessions.keys()):
        if session_id.startswith("test-"):
            store.delete_session(session_id)


@pytest.fixture
def test_optimize_request() -> Dict[str, Any]:
    """Provide sample optimize request"""
    return {
        "schema_version": "optimize_request.v1",
        "session_id": None,
        "user_request": "Design a microstrip patch antenna at 2.45 GHz",
        "target_spec": {
            "frequency_ghz": 2.45,
            "bandwidth_mhz": 100.0,
            "antenna_family": "microstrip_patch"
        },
        "design_constraints": {
            "allowed_materials": ["Copper (annealed)"],
            "allowed_substrates": ["FR-4 (lossy)"]
        },
        "optimization_policy": {
            "mode": "auto_iterate",
            "max_iterations": 5,
            "stop_on_first_valid": True,
            "acceptance": {
                "center_tolerance_mhz": 20.0,
                "minimum_bandwidth_mhz": 80.0,
                "maximum_vswr": 2.0,
                "minimum_gain_dbi": 0.0
            },
            "fallback_behavior": "best_effort"
        },
        "runtime_preferences": {
            "require_explanations": False,
            "persist_artifacts": True,
            "llm_temperature": 0.0,
            "timeout_budget_sec": 300
        },
        "client_capabilities": {
            "supports_farfield_export": True,
            "supports_current_distribution_export": False,
            "supports_parameter_sweep": False,
            "max_simulation_timeout_sec": 600,
            "export_formats": ["json"]
        }
    }


@pytest.fixture
def test_feedback_payload() -> Dict[str, Any]:
    """Provide sample feedback payload"""
    return {
        "schema_version": "client_feedback.v1",
        "session_id": "test-session-001",
        "trace_id": "trace-001",
        "design_id": "design-001",
        "iteration_index": 0,
        "simulation_status": "completed",
        "actual_center_frequency_ghz": 2.44,
        "actual_bandwidth_mhz": 98.5,
        "actual_return_loss_db": -18.2,
        "actual_vswr": 1.48,
        "actual_gain_dbi": 4.6,
        "notes": "Iteration 0: Simulation successful",
        "artifacts": {
            "s11_trace_ref": "artifacts/s11_iter0.json",
            "summary_metrics_ref": "artifacts/summary_iter0.json",
            "farfield_ref": None,
            "current_distribution_ref": None,
        }
    }


@pytest.fixture
async def client_initializer(mock_connector):
    """Provide client initializer with mock connector"""
    # This is a mock version for testing
    initializer = ClientInitializer(mock_connector)
    return initializer


# Helper functions for testing

def create_test_session(store: SessionStore, session_id: Optional[str] = None) -> str:
    """Helper to create test session"""
    session = store.create_session(
        f"Test session {session_id}",
        session_id=session_id or "test-session-001",
        trace_id="trace-001",
        design_id="design-001"
    )
    return session.session_id


def load_sample_payload(payload_type: str) -> Dict[str, Any]:
    """Load sample payload from file"""
    samples_dir = Path(__file__).parent.parent / "artifacts" / "samples"
    
    if payload_type == "optimize_request":
        return {
            "schema_version": "optimize_request.v1",
            "user_request": "Design antenna",
            "target_spec": {"frequency_ghz": 2.45, "bandwidth_mhz": 100.0, "antenna_family": "microstrip_patch"},
            "design_constraints": {"allowed_materials": ["Copper (annealed)"],"allowed_substrates": ["FR-4 (lossy)"]},
            "optimization_policy": {"mode": "auto_iterate", "max_iterations": 5, "stop_on_first_valid": True},
            "runtime_preferences": {"require_explanations": False, "persist_artifacts": True},
            "client_capabilities": {"supports_farfield_export": True}
        }
    
    return {}


def assert_payload_schema(payload: Dict[str, Any], required_fields: list) -> bool:
    """Assert payload has required fields"""
    for field in required_fields:
        assert field in payload, f"Missing required field: {field}"
    return True


# Pytest configuration

def pytest_configure(config):
    """Configure pytest"""
    # Add markers
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
