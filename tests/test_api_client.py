"""
Test API client functionality
"""

import pytest
from comm.request_builder import OptimizeRequest
from comm.api_client import OptimizeResponse, ApiClient
from comm.server_connector import ServerConnector
from utils.logger import get_logger


@pytest.mark.asyncio
async def test_optimize_request_creation():
    """Test OptimizeRequest creation"""
    request = OptimizeRequest(
        user_request="Design 2.4 GHz patch antenna",
        design_specs={"frequency_ghz": 2.4, "bandwidth_mhz": 50}
    )
    
    assert request.user_request == "Design 2.4 GHz patch antenna"
    assert request.design_specs["frequency_ghz"] == 2.4


def test_optimize_response_parsing():
    """Test OptimizeResponse parsing"""
    response_data = {
        "status": "success",
        "command_package": {"version": "1.0", "commands": []},
        "clarification": None
    }
    
    response = OptimizeResponse(**response_data)
    assert response.status == "success"
    assert response.command_package is not None
