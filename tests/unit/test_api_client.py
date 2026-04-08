"""Test API client functionality."""

from comm.error_handler import ErrorCode, ErrorHandler
from comm.request_builder import RequestBuilder
from comm.api_client import OptimizeResponse


def test_optimize_request_creation():
    """Test OptimizeRequest creation."""
    request = RequestBuilder().build_optimize_request(
        user_text="Design 2.4 GHz patch antenna",
        design_specs={"frequency_ghz": 2.4, "bandwidth_mhz": 50.0, "antenna_family": "microstrip_patch"},
    )

    assert request.user_request == "Design 2.4 GHz patch antenna"
    assert request.target_spec["frequency_ghz"] == 2.4
    assert request.target_spec["bandwidth_mhz"] == 50.0
    assert request.target_spec["antenna_family"] == "microstrip_patch"


def test_optimize_response_parsing():
    """Test OptimizeResponse parsing."""
    response_data = {
        "status": "accepted",
        "command_package": {"schema_version": "cst_command_package.v2", "commands": []},
        "clarification": None,
    }

    response = OptimizeResponse(**response_data)
    assert response.status == "accepted"
    assert response.command_package is not None


def test_v2_validation_error_parsing_includes_details() -> None:
    error_code, user_msg, recoverable, action = ErrorHandler.parse_error(
        {
            "error_code": "V2_COMMAND_VALIDATION_FAILED",
            "message": "Command 3:define_brick missing required params: component",
            "details": {
                "command_index": 3,
                "command_name": "define_brick",
                "invalid_fields": ["component"],
            },
        }
    )

    assert error_code == ErrorCode.V2_COMMAND_VALIDATION_FAILED
    assert recoverable is True
    assert action == "review_server_command_package"
    assert "command_index=3" in user_msg
    assert "command_name=define_brick" in user_msg
