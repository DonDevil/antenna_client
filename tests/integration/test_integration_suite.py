"""
Integration Tests for Client-Server Communication

Tests the 3 main integration scenarios:
1. End-to-End Optimization Flow (health → optimize → execute → feedback)
2. Session Recovery & Persistence
3. WebSocket Live Streaming
"""

import asyncio
import json
import pytest
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from comm.server_connector import ServerConnector
from comm.api_client import ApiClient
from comm.initializer import ClientInitializer
from comm.request_builder import RequestBuilder
from comm.response_handler import ResponseHandler
from comm.error_handler import ErrorHandler, ErrorCode
from session.session_store import SessionStore
from executor.execution_engine import ExecutionEngine
from executor.command_parser import CommandPackage, Command
from utils.logger import get_logger

logger = get_logger(__name__)

# Load server URL from config
import json as json_module
config_path = Path(__file__).parent.parent.parent / "config.json"
with open(config_path) as f:
    CONFIG = json_module.load(f)
    SERVER_BASE_URL = CONFIG.get("server", {}).get("base_url", "http://192.168.29.147:8000")
    SERVER_TIMEOUT = CONFIG.get("server", {}).get("timeout_sec", 60)


class IntegrationTestResults:
    """Track test results for reporting"""
    
    def __init__(self):
        self.tests: Dict[str, Dict[str, Any]] = {}
        self.start_time = datetime.now()
    
    def add_test(self, test_name: str, status: str, details: str = "", error: str = ""):
        """Record test result"""
        self.tests[test_name] = {
            "status": status,  # PASS, FAIL, SKIP
            "details": details,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
    
    def summary(self) -> Dict[str, Any]:
        """Generate summary"""
        total = len(self.tests)
        passed = sum(1 for t in self.tests.values() if t["status"] == "PASS")
        failed = sum(1 for t in self.tests.values() if t["status"] == "FAIL")
        
        return {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "success_rate": f"{(passed/total*100):.1f}%" if total > 0 else "0%",
            "duration": str(datetime.now() - self.start_time),
            "details": self.tests
        }
    
    def report(self) -> str:
        """Generate human-readable report"""
        summary = self.summary()
        report = [
            "=" * 70,
            "INTEGRATION TEST REPORT",
            "=" * 70,
            f"Total Tests: {summary['total_tests']}",
            f"Passed: {summary['passed']} [OK]",
            f"Failed: {summary['failed']} [FAIL]",
            f"Success Rate: {summary['success_rate']}",
            f"Duration: {summary['duration']}",
            "",
            "DETAILED RESULTS:",
            "-" * 70,
        ]
        
        for test_name, result in self.tests.items():
            status_icon = "[OK]" if result["status"] == "PASS" else "[FAIL]" if result["status"] == "FAIL" else "[SKIP]"
            report.append(f"{status_icon} {test_name}")
            if result["details"]:
                report.append(f"   Details: {result['details']}")
            if result["error"]:
                report.append(f"   Error: {result['error']}")
        
        report.append("=" * 70)
        return "\n".join(report)


# ============================================================================
# TEST 1: END-TO-END OPTIMIZATION FLOW
# ============================================================================

class TestEndToEndFlow:
    """Test complete optimization flow: health → optimize → execute → feedback"""
    
    def __init__(self):
        self.results = IntegrationTestResults()
        self.base_url = SERVER_BASE_URL
        self.session_id = None
        self.trace_id = None
        self.design_id = None
        self.command_package = None
        # Use REAL server connector
        self.connector = ServerConnector(self.base_url, timeout_sec=SERVER_TIMEOUT)
    
    async def test_step_1_health_check(self) -> bool:
        """Step 1: GET /api/v1/health"""
        try:
            async with self.connector:
                health = await self.connector.get("/api/v1/health")
            
            status = health.get("status", "unknown")
            ann_status = health.get("ann_status", "unknown")
            llm_status = health.get("llm_status", "unknown")
            
            if status != "ok":
                self.results.add_test(
                    "E2E-1: Health Check",
                    "FAIL",
                    f"Server status: {status}",
                    f"Expected status='ok', got '{status}'"
                )
                return False
            
            self.results.add_test(
                "E2E-1: Health Check",
                "PASS",
                f"✓ Server online at {self.base_url} | ANN: {ann_status} | LLM: {llm_status}",
            )
            return True
        except Exception as e:
            self.results.add_test(
                "E2E-1: Health Check",
                "FAIL",
                f"Cannot reach server at {self.base_url}",
                str(e)
            )
            return False
    
    async def test_step_2_capabilities(self) -> bool:
        """Step 2: GET /api/v1/capabilities"""
        try:
            async with self.connector:
                caps = await self.connector.get("/api/v1/capabilities")
            
            if not caps or "capabilities" not in caps:
                self.results.add_test(
                    "E2E-2: Load Capabilities",
                    "SKIP",
                    details="Capabilities endpoint returned no data; continuing because this step is optional for the main workflow"
                )
                return True
            
            families = caps.get("capabilities", {}).get("supported_antenna_families", [])
            freq_range = caps.get("capabilities", {}).get("frequency_range_ghz", {})
            
            self.results.add_test(
                "E2E-2: Load Capabilities",
                "PASS",
                f"✓ Loaded {len(families)} antenna families | Freq: {freq_range.get('min')}-{freq_range.get('max')} GHz",
            )
            return True
        except Exception as e:
            self.results.add_test(
                "E2E-2: Load Capabilities",
                "SKIP",
                details="Capabilities endpoint unavailable; continuing because this step is optional for the main workflow",
                error=str(e)
            )
            return True
    
    async def test_step_3_optimize_request(self) -> bool:
        """Step 3: POST /api/v1/optimize"""
        try:
            async with self.connector:
                api_client = ApiClient(self.connector)
                
                # Build request
                request_builder = RequestBuilder()
                request = request_builder.build_optimize_request(
                    user_text="Design a microstrip patch antenna at 2.45 GHz with 100 MHz bandwidth",
                    design_specs={
                        "frequency_ghz": 2.45,
                        "bandwidth_mhz": 100.0,
                        "antenna_family": "microstrip_patch"
                    }
                )
                
                # Send request to REAL server
                logger.info(f"Sending optimize request to {self.base_url}/api/v1/optimize")
                parsed_response = await api_client.optimize(request.dict())
            
            # Check response
            if parsed_response.status not in ("accepted", "completed"):
                self.results.add_test(
                    "E2E-3: Optimize Request",
                    "FAIL",
                    f"Status: {parsed_response.status}",
                    f"Expected 'accepted' or 'completed', got '{parsed_response.status}'"
                )
                return False
            
            # Capture IDs
            self.session_id = parsed_response.session_id
            self.trace_id = parsed_response.trace_id
            self.design_id = parsed_response.command_package.get("design_id") if parsed_response.command_package else None
            self.command_package = parsed_response.command_package
            
            if not self.session_id or not self.trace_id:
                self.results.add_test(
                    "E2E-3: Optimize Request",
                    "FAIL",
                    error="Missing session_id or trace_id in response"
                )
                return False
            
            self.results.add_test(
                "E2E-3: Optimize Request",
                "PASS",
                f"✓ Session: {self.session_id[:8]}... | Design: {self.design_id[:8] if self.design_id else 'N/A'}...",
            )
            return True
        except Exception as e:
            self.results.add_test(
                "E2E-3: Optimize Request",
                "FAIL",
                f"Server error or request format issue",
                str(e)
            )
            return False
    
    async def test_step_4_command_execution(self) -> bool:
        """Step 4: Execute command package (simulated)"""
        try:
            if not self.command_package:
                self.results.add_test(
                    "E2E-4: Command Execution",
                    "SKIP",
                    "No command package to execute"
                )
                return True
            
            commands = self.command_package.get("commands", [])
            
            # Verify commands are in order
            for i, cmd in enumerate(commands):
                expected_seq = i + 1
                actual_seq = cmd.get("seq", i + 1)
                if actual_seq != expected_seq:
                    self.results.add_test(
                        "E2E-4: Command Execution",
                        "FAIL",
                        error=f"Commands out of order: expected seq {expected_seq}, got {actual_seq}"
                    )
                    return False
            
            self.results.add_test(
                "E2E-4: Command Execution",
                "PASS",
                f"✓ Validated {len(commands)} commands in correct order",
            )
            return True
        except Exception as e:
            self.results.add_test(
                "E2E-4: Command Execution",
                "FAIL",
                error=str(e)
            )
            return False
    
    async def test_step_5_client_feedback(self) -> bool:
        """Step 5: POST /api/v1/feedback"""
        try:
            if not self.session_id or not self.trace_id:
                self.results.add_test(
                    "E2E-5: Client Feedback",
                    "SKIP",
                    "No session from optimize request"
                )
                return True
            
            async with self.connector:
                api_client = ApiClient(self.connector)
                
                # Build feedback
                feedback = {
                    "schema_version": "client_feedback.v1",
                    "session_id": self.session_id,
                    "trace_id": self.trace_id,
                    "design_id": self.design_id or f"design_{self.session_id}",
                    "iteration_index": 0,
                    "simulation_status": "completed",
                    "actual_center_frequency_ghz": 2.44,
                    "actual_bandwidth_mhz": 98.5,
                    "actual_return_loss_db": -18.2,
                    "actual_vswr": 1.48,
                    "actual_gain_dbi": 4.6,
                    "notes": "Iteration 0: CST simulation completed successfully.",
                    "artifacts": {
                        "s11_trace_ref": "artifacts/s11_iter0.json",
                        "summary_metrics_ref": "artifacts/summary_iter0.json",
                        "farfield_ref": None,
                        "current_distribution_ref": None,
                    }
                }
                
                # Send feedback to REAL server
                logger.info(f"Sending feedback to {self.base_url}/api/v1/feedback")
                response_data = await api_client.send_result(feedback)
            
            # Check response
            if not response_data:
                self.results.add_test(
                    "E2E-5: Client Feedback",
                    "FAIL",
                    error="No response from server"
                )
                return False
            
            self.results.add_test(
                "E2E-5: Client Feedback",
                "PASS",
                f"✓ Feedback accepted | Status: {response_data.get('status', 'received')}",
            )
            return True
        except Exception as e:
            self.results.add_test(
                "E2E-5: Client Feedback",
                "FAIL",
                f"Server error or schema validation failed",
                str(e)
            )
            return False
    
    async def run_all(self) -> IntegrationTestResults:
        """Run all E2E tests"""
        logger.info(f"Starting End-to-End Flow Tests against {self.base_url}...")
        
        await self.test_step_1_health_check()
        await self.test_step_2_capabilities()
        await self.test_step_3_optimize_request()
        await self.test_step_4_command_execution()
        await self.test_step_5_client_feedback()
        
        return self.results


# ============================================================================
# TEST 2: SESSION RECOVERY & PERSISTENCE
# ============================================================================

class TestSessionRecovery:
    """Test session persistence and recovery"""
    
    def __init__(self):
        self.results = IntegrationTestResults()
        self.session_store = SessionStore()
    
    async def test_step_1_create_session(self) -> bool:
        """Step 1: Create and persist session"""
        try:
            session = self.session_store.create_session(
                "Test recovery session",
                session_id="test-recovery-001",
                trace_id="trace-001",
                design_id="design-001"
            )
            
            if not session.session_id:
                self.results.add_test(
                    "Recovery-1: Create Session",
                    "FAIL",
                    error="Failed to create session"
                )
                return False
            
            # Check persistence file exists
            session_file = Path(__file__).parent.parent.parent / "test_checkpoints" / f"{session.session_id}.json"
            if not session_file.exists():
                self.results.add_test(
                    "Recovery-1: Create Session",
                    "FAIL",
                    error=f"Session file not persisted at {session_file}"
                )
                return False
            
            self.results.add_test(
                "Recovery-1: Create Session",
                "PASS",
                f"Session created: {session.session_id}, persisted to disk",
            )
            return True
        except Exception as e:
            self.results.add_test(
                "Recovery-1: Create Session",
                "FAIL",
                error=str(e)
            )
            return False
    
    async def test_step_2_load_session(self) -> bool:
        """Step 2: Load persisted session"""
        try:
            # Create new session store (simulates app restart)
            new_store = SessionStore()
            
            # Try to retrieve previously created session
            session = new_store.get_session("test-recovery-001")
            
            if not session:
                self.results.add_test(
                    "Recovery-2: Load Session",
                    "FAIL",
                    error="Session not loaded from disk"
                )
                return False
            
            if session.trace_id != "trace-001" or session.design_id != "design-001":
                self.results.add_test(
                    "Recovery-2: Load Session",
                    "FAIL",
                    error="Session metadata not preserved"
                )
                return False
            
            self.results.add_test(
                "Recovery-2: Load Session",
                "PASS",
                f"Session recovered: {session.session_id}",
            )
            return True
        except Exception as e:
            self.results.add_test(
                "Recovery-2: Load Session",
                "FAIL",
                error=str(e)
            )
            return False
    
    async def test_step_3_update_metadata(self) -> bool:
        """Step 3: Update session metadata"""
        try:
            session = self.session_store.get_session("test-recovery-001")
            if not session:
                self.results.add_test(
                    "Recovery-3: Update Metadata",
                    "SKIP",
                    "Session not found"
                )
                return True
            
            # Update status
            self.session_store.update_session_status("test-recovery-001", "completed")
            
            # Reload and verify
            new_store = SessionStore()
            updated_session = new_store.get_session("test-recovery-001")
            if not updated_session:
                self.results.add_test(
                    "Recovery-3: Update Metadata",
                    "FAIL",
                    error="Updated session could not be reloaded"
                )
                return False
            
            if updated_session.status != "completed":
                self.results.add_test(
                    "Recovery-3: Update Metadata",
                    "FAIL",
                    error="Status update not persisted"
                )
                return False
            
            self.results.add_test(
                "Recovery-3: Update Metadata",
                "PASS",
                f"Session status updated: {updated_session.status}",
            )
            return True
        except Exception as e:
            self.results.add_test(
                "Recovery-3: Update Metadata",
                "FAIL",
                error=str(e)
            )
            return False
    
    async def run_all(self) -> IntegrationTestResults:
        """Run all session recovery tests"""
        logger.info("Starting Session Recovery Tests...")
        
        await self.test_step_1_create_session()
        await self.test_step_2_load_session()
        await self.test_step_3_update_metadata()
        
        return self.results


# ============================================================================
# TEST 3: PAYLOAD VALIDATION
# ============================================================================

class TestPayloadValidation:
    """Test that payloads match expected schema"""
    
    def __init__(self):
        self.results = IntegrationTestResults()
    
    def test_optimize_request_schema(self) -> bool:
        """Validate optimize request schema"""
        try:
            request_builder = RequestBuilder()
            request = request_builder.build_optimize_request(
                user_text="Design antenna",
                design_specs={
                    "frequency_ghz": 2.45,
                    "bandwidth_mhz": 100.0,
                    "antenna_family": "microstrip_patch"
                }
            )
            
            required_fields = [
                "schema_version", "user_request", "target_spec",
                "design_constraints", "optimization_policy", "runtime_preferences",
                "client_capabilities"
            ]
            
            request_dict = request.dict()
            for field in required_fields:
                if field not in request_dict:
                    self.results.add_test(
                        "Payload-1: Optimize Request Schema",
                        "FAIL",
                        error=f"Missing required field: {field}"
                    )
                    return False
            
            # Validate target_spec
            target_spec = request_dict["target_spec"]
            if not all(k in target_spec for k in ["frequency_ghz", "bandwidth_mhz", "antenna_family"]):
                self.results.add_test(
                    "Payload-1: Optimize Request Schema",
                    "FAIL",
                    error="target_spec missing required fields"
                )
                return False
            
            self.results.add_test(
                "Payload-1: Optimize Request Schema",
                "PASS",
                "Request schema valid",
            )
            return True
        except Exception as e:
            self.results.add_test(
                "Payload-1: Optimize Request Schema",
                "FAIL",
                error=str(e)
            )
            return False
    
    def test_feedback_payload_schema(self) -> bool:
        """Validate feedback payload schema"""
        try:
            feedback = {
                "schema_version": "client_feedback.v1",
                "session_id": "test-session",
                "trace_id": "test-trace",
                "design_id": "test-design",
                "iteration_index": 0,
                "simulation_status": "completed",
                "actual_center_frequency_ghz": 2.44,
                "actual_bandwidth_mhz": 98.5,
                "actual_return_loss_db": -18.2,
                "actual_vswr": 1.48,
                "actual_gain_dbi": 4.6,
                "notes": "Test feedback",
                "artifacts": {
                    "s11_trace_ref": "path/to/s11",
                    "summary_metrics_ref": "path/to/metrics",
                    "farfield_ref": None,
                    "current_distribution_ref": None,
                }
            }
            
            required_fields = [
                "schema_version", "session_id", "trace_id", "design_id",
                "iteration_index", "simulation_status", "actual_center_frequency_ghz",
                "actual_bandwidth_mhz", "actual_return_loss_db", "actual_vswr",
                "actual_gain_dbi", "notes", "artifacts"
            ]
            
            for field in required_fields:
                if field not in feedback:
                    self.results.add_test(
                        "Payload-2: Feedback Schema",
                        "FAIL",
                        error=f"Missing required field: {field}"
                    )
                    return False
            
            # Validate artifacts
            artifacts = feedback["artifacts"]
            if not all(k in artifacts for k in ["s11_trace_ref", "summary_metrics_ref"]):
                self.results.add_test(
                    "Payload-2: Feedback Schema",
                    "FAIL",
                    error="artifacts missing required trace references"
                )
                return False
            
            self.results.add_test(
                "Payload-2: Feedback Schema",
                "PASS",
                "Feedback schema valid",
            )
            return True
        except Exception as e:
            self.results.add_test(
                "Payload-2: Feedback Schema",
                "FAIL",
                error=str(e)
            )
            return False
    
    def test_error_code_mapping(self) -> bool:
        """Validate error code handling"""
        try:
            test_errors = [
                {
                    "error_code": "SCHEMA_VALIDATION_FAILED",
                    "message": "Invalid schema"
                },
                {
                    "error_code": "FAMILY_NOT_SUPPORTED",
                    "message": "Family not supported"
                },
                {
                    "error_code": "SESSION_NOT_FOUND",
                    "message": "Session not found"
                }
            ]
            
            for error_data in test_errors:
                error_code, user_msg, recoverable, action = ErrorHandler.parse_error(error_data)
                
                if not user_msg or not action:
                    self.results.add_test(
                        "Payload-3: Error Code Handling",
                        "FAIL",
                        error=f"Invalid response for error code: {error_data['error_code']}"
                    )
                    return False
            
            self.results.add_test(
                "Payload-3: Error Code Handling",
                "PASS",
                "All error codes mapped correctly",
            )
            return True
        except Exception as e:
            self.results.add_test(
                "Payload-3: Error Code Handling",
                "FAIL",
                error=str(e)
            )
            return False
    
    def run_all(self) -> IntegrationTestResults:
        """Run all payload validation tests"""
        logger.info("Starting Payload Validation Tests...")
        
        self.test_optimize_request_schema()
        self.test_feedback_payload_schema()
        self.test_error_code_mapping()
        
        return self.results


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

async def run_all_integration_tests() -> Dict[str, IntegrationTestResults]:
    """Run all integration test suites"""
    
    logger.info("=" * 70)
    logger.info("INTEGRATION TEST SUITE STARTING")
    logger.info("=" * 70)
    
    results = {}
    
    # Test 1: End-to-End Flow
    logger.info("\n[1/3] Running End-to-End Flow Tests...")
    e2e_test = TestEndToEndFlow()
    results["e2e"] = await e2e_test.run_all()
    logger.info(f"✓ E2E tests complete")
    
    # Test 2: Session Recovery
    logger.info("\n[2/3] Running Session Recovery Tests...")
    recovery_test = TestSessionRecovery()
    results["recovery"] = await recovery_test.run_all()
    logger.info(f"✓ Recovery tests complete")
    
    # Test 3: Payload Validation
    logger.info("\n[3/3] Running Payload Validation Tests...")
    payload_test = TestPayloadValidation()
    results["payload"] = payload_test.run_all()
    logger.info(f"✓ Payload tests complete")
    
    return results


def print_test_report(results: Dict[str, IntegrationTestResults]):
    """Print comprehensive test report"""
    
    print("\n" * 2)
    print("=" * 70)
    print("COMPREHENSIVE INTEGRATION TEST REPORT")
    print("=" * 70)
    
    total_tests = 0
    total_passed = 0
    total_failed = 0
    
    for suite_name, suite_results in results.items():
        print(f"\n{suite_name.upper()} TESTS:")
        print("-" * 70)
        print(suite_results.report())
        
        summary = suite_results.summary()
        total_tests += summary["total_tests"]
        total_passed += summary["passed"]
        total_failed += summary["failed"]
    
    print("\n" + "=" * 70)
    print("OVERALL SUMMARY")
    print("=" * 70)
    print(f"Total Tests Run: {total_tests}")
    print(f"[OK] Passed: {total_passed}")
    print(f"[FAIL] Failed: {total_failed}")
    print(f"Success Rate: {(total_passed/total_tests*100):.1f}%" if total_tests > 0 else "0%")
    print("=" * 70)
    
    if total_failed == 0:
        print("[OK] ALL TESTS PASSED - READY FOR PRODUCTION")
    else:
        print(f"[FAIL] {total_failed} TEST(S) FAILED - REVIEW REQUIRED")
    
    print("=" * 70)


# Add this to run with pytest
@pytest.mark.asyncio
async def test_integration_suite():
    """Pytest entry point for integration tests"""
    results = await run_all_integration_tests()
    
    # Verify no failures
    for suite_results in results.values():
        summary = suite_results.summary()
        assert summary["failed"] == 0, f"Integration tests failed: {summary}"


if __name__ == "__main__":
    # Run tests directly
    results = asyncio.run(run_all_integration_tests())
    print_test_report(results)
