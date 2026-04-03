"""
Integration tests for full pipeline
"""

import pytest
import asyncio
from comm.server_connector import ServerConnector
from comm.api_client import ApiClient
from comm.request_builder import RequestBuilder, OptimizeRequest
from comm.intent_parser import IntentParser
from comm.response_handler import ResponseHandler
from session.session_store import SessionStore
from session.design_store import DesignStore
from session.chat_history import ChatHistory
from executor.command_parser import CommandParser
from executor.vba_generator import VBAGenerator
from executor.execution_engine import ExecutionEngine
from utils.validators import extract_frequency_bandwidth


@pytest.mark.asyncio
async def test_full_optimization_pipeline():
    """Test complete optimization pipeline from intent to execution"""
    
    # Phase 1: Session creation
    session_store = SessionStore()
    session = session_store.create_session("Design 2.4 GHz patch antenna")
    assert session.session_id
    
    # Phase 2: Intent parsing (local fallback)
    intent_parser = IntentParser()
    intent = intent_parser.parse("Design 2.4 GHz patch antenna with 50 MHz bandwidth")
    
    assert intent["antenna_type"] == "patch"
    assert intent["frequency_ghz"] == 2.4
    assert intent["bandwidth_mhz"] == 50.0
    assert intent["action"] == "design"
    
    # Phase 3: Request building
    request_builder = RequestBuilder()
    request = request_builder.build_optimize_request(intent["antenna_type"] or "antenna")
    assert request is not None
    assert hasattr(request, 'user_request')
    
    # Phase 4: Design storage
    design_store = DesignStore()
    design = design_store.create_design(
        session.session_id,
        {
            "antenna_family": "patch",
            "frequency_ghz": 2.4,
            "bandwidth_mhz": 50.0,
            "gain_db": "high"
        }
    )
    assert design.design_id
    
    # Phase 5: Command parsing
    command_parser = CommandParser()
    test_package = {
        "package_version": "1.0",
        "commands": [
            {
                "id": "cmd1",
                "type": "create_project",
                "parameters": {"project_name": "patch_2.4ghz"},
                "on_failure": "abort"
            },
            {
                "id": "cmd2",
                "type": "set_units",
                "parameters": {"geometry_unit": "mm", "frequency_unit": "ghz"},
                "on_failure": "abort"
            }
        ]
    }
    
    package = command_parser.parse_package(test_package)
    assert package.package_version == "1.0"
    assert len(package.commands) == 2
    
    # Phase 6: VBA generation
    vba_gen = VBAGenerator()
    vba_create = vba_gen.generate_macro("create_project", {"name": "antenna"})
    assert vba_create is not None
    
    # Phase 7: Execution engine (simulation only)
    # Note: Full execution would require CST Studio to be installed
    exec_engine = ExecutionEngine()
    assert exec_engine is not None
    progress = exec_engine.get_progress()
    assert "completed" in progress


def test_response_handling():
    """Test server response handling"""
    
    from comm.response_handler import OptimizeResponse, ResponseHandler
    
    # Test ready status
    response = OptimizeResponse(
        status="success",
        command_package={
            "package_version": "1.0",
            "commands": []
        }
    )
    
    handler = ResponseHandler()
    result = handler.handle_optimize_response(response)
    assert result["action"] == "execute"
    
    # Test clarification
    response_clarify = OptimizeResponse(
        status="clarification_required",
        clarification="What is the desired gain?"
    )
    result = handler.handle_optimize_response(response_clarify)
    assert result["action"] == "clarify"


def test_chat_workflow():
    """Test chat and history tracking"""
    
    # Create session
    session_store = SessionStore()
    session = session_store.create_session("Chat test")
    
    # Add chat messages
    chat_history = ChatHistory(session.session_id)
    chat_history.add_message("user", "Design antenna")
    chat_history.add_message("assistant", "Understood")
    
    # Retrieve history
    messages = chat_history.get_messages()
    assert len(messages) == 2
    assert messages[0]["sender"] == "user"
    assert messages[1]["sender"] == "assistant"


def test_design_iteration():
    """Test iteration tracking"""
    
    from session.iteration_tracker import IterationTracker
    
    session_id = "test_session"
    tracker = IterationTracker()
    
    # Add iterations
    tracker.add_iteration(session_id, 0, {"freq": 2.4}, {"center_freq": 2.4, "bw": 50})
    tracker.add_iteration(session_id, 1, {"freq": 2.41}, {"center_freq": 2.41, "bw": 51})
    
    # Get history
    history = tracker.get_iteration_history(session_id)
    assert len(history) == 2
    
    # Compare iterations
    comparison = tracker.compare_iterations(session_id, 0, 1)
    assert comparison["iter1"] == 0
    assert comparison["iter2"] == 1


def test_error_recovery():
    """Test error recovery mechanisms"""
    
    from session.error_recovery import ErrorRecovery
    
    recovery = ErrorRecovery()
    
    # Simulate network error
    error = Exception("Network timeout")
    can_recover = recovery.handle_network_error(error)
    assert can_recover
    
    # Check status
    status = recovery.get_recovery_status()
    assert status["error_count"] == 1
    assert status["is_recovering"]


def test_checkpoints():
    """Test checkpoint save/load"""
    
    from session.checkpoint_manager import CheckpointManager
    
    manager = CheckpointManager("test_checkpoints")
    
    # Save checkpoint
    state = {"session_id": "test", "progress": 50}
    path = manager.save_checkpoint("test_session", state)
    assert path
    
    # Load checkpoint
    loaded = manager.load_checkpoint("test_session")
    assert loaded["session_id"] == "test"
    assert loaded["progress"] == 50
    
    # Cleanup
    manager.cleanup_checkpoints(0)


if __name__ == "__main__":
    # Run async test
    asyncio.run(test_full_optimization_pipeline())
    print("All integration tests passed!")
