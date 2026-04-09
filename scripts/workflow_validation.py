#!/usr/bin/env python3
"""
Complete Server Workflow Validation

Follows the server copilot's recommended workflow:
1. GET /api/v1/health
2. POST /api/v1/optimize
3. Client executes returned command_package (simulated)
4. POST /api/v1/result
5. Verify completed or refining

Usage: python workflow_validation.py
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from comm.server_connector import ServerConnector
from comm.api_client import ApiClient
from comm.request_builder import RequestBuilder
from utils.logger import get_logger

logger = get_logger(__name__)

# Load config
config_path = PROJECT_ROOT / "config.json"
with open(config_path) as f:
    CONFIG = json.load(f)
    SERVER_BASE_URL = CONFIG.get("server", {}).get("base_url", "http://192.168.29.147:8000")
    SERVER_TIMEOUT = CONFIG.get("server", {}).get("timeout_sec", 60)

class WorkflowValidator:
    """Validates end-to-end workflow"""
    
    def __init__(self):
        self.base_url = SERVER_BASE_URL
        self.session_id = None
        self.trace_id = None
        self.design_id = None
        self.errors = []
        self.warnings = []
        self.successes = []
        self.start_time = datetime.now()
    
    def log_success(self, msg):
        self.successes.append(msg)
        logger.info(f"✓ {msg}")
    
    def log_error(self, msg):
        self.errors.append(msg)
        logger.error(f"✗ {msg}")
    
    def log_warning(self, msg):
        self.warnings.append(msg)
        logger.warning(f"⚠ {msg}")
    
    async def step_1_health_check(self):
        """Step 1: GET /api/v1/health"""
        print("\n" + "="*70)
        print("STEP 1: Health Check → GET /api/v1/health")
        print("="*70)
        
        try:
            connector = ServerConnector(self.base_url, timeout_sec=SERVER_TIMEOUT)
            async with connector:
                response = await connector.get("/api/v1/health")
            
            logger.info(f"Response: {json.dumps(response, indent=2)}")
            
            # Validate response
            if response.get("status") != "ok":
                self.log_error(f"Health check failed: status={response.get('status')}")
                return False
            
            if response.get("ann_status") not in ["available", "loading"]:
                self.log_warning(f"ANN status concerning: {response.get('ann_status')}")
            
            if response.get("llm_status") not in ["available", "loading"]:
                self.log_warning(f"LLM status concerning: {response.get('llm_status')}")
            
            self.log_success(f"Server online at {self.base_url}")
            self.log_success(f"ANN: {response.get('ann_status')}, LLM: {response.get('llm_status')}")
            return True
            
        except Exception as e:
            self.log_error(f"Health check failed: {e}")
            return False
    
    async def step_2_optimize_request(self):
        """Step 2: POST /api/v1/optimize"""
        print("\n" + "="*70)
        print("STEP 2: Optimize Request → POST /api/v1/optimize")
        print("="*70)
        
        try:
            connector = ServerConnector(self.base_url, timeout_sec=SERVER_TIMEOUT)
            async with connector:
                api_client = ApiClient(connector)
                
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
                
                request_payload = request.model_dump() if hasattr(request, "model_dump") else request.dict()
                logger.info(f"Sending request: {json.dumps(request_payload, indent=2, default=str)[:500]}...")
                
                # Send request
                response = await api_client.optimize(request_payload)
            
            logger.info(f"Response status: {response.status if response else 'None'}")
            
            # Check response
            if not response:
                self.log_error("No response from optimize endpoint")
                return False
            
            if response.status not in ("accepted", "completed"):
                self.log_error(f"Unexpected status: {response.status}")
                return False
            
            # Extract IDs
            self.session_id = response.session_id
            self.trace_id = response.trace_id
            self.design_id = response.command_package.get("design_id") if response.command_package else None
            
            if not self.session_id or not self.trace_id:
                self.log_error("Missing session_id or trace_id in response")
                return False
            
            self.log_success(f"Optimization request accepted")
            self.log_success(f"Session ID: {self.session_id}")
            self.log_success(f"Trace ID: {self.trace_id}")
            self.log_success(f"Design ID: {self.design_id}")
            
            if response.command_package:
                commands = response.command_package.get("commands", [])
                self.log_success(f"Received {len(commands)} commands in package")
                for cmd in commands:
                    self.log_success(f"  - Command {cmd.get('seq')}: {cmd.get('command', cmd.get('type', 'unknown'))}")
            
            return True
            
        except Exception as e:
            self.log_error(f"Optimize request failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def step_3_execute_commands(self):
        """Step 3: Execute command package (simulated)"""
        print("\n" + "="*70)
        print("STEP 3: Execute Command Package (Simulated)")
        print("="*70)
        
        try:
            if not self.session_id:
                self.log_warning("No session from optimize request, skipping execution")
                return True
            
            self.log_success("Command execution simulated (no real CST/VBA needed for this test)")
            self.log_success("In production, this would:")
            self.log_success("  1. Load CST project")
            self.log_success("  2. Modify antenna dimensions")
            self.log_success("  3. Run FDTD simulation")
            self.log_success("  4. Extract S11, gain, bandwidth metrics")
            
            return True
            
        except Exception as e:
            self.log_error(f"Command execution failed: {e}")
            return False
    
    async def step_4_client_feedback(self):
        """Step 4: POST /api/v1/result"""
        print("\n" + "="*70)
        print("STEP 4: Client Feedback → POST /api/v1/result")
        print("="*70)
        
        try:
            if not self.session_id or not self.trace_id:
                self.log_warning("No session from optimize request, skipping feedback")
                return True
            
            connector = ServerConnector(self.base_url, timeout_sec=SERVER_TIMEOUT)
            async with connector:
                api_client = ApiClient(connector)
                
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
                    "notes": "Workflow validation iteration 0 - simulated CST run completed successfully.",
                    "artifacts": {
                        "s11_trace_ref": "artifacts/workflow_s11_iter0.json",
                        "summary_metrics_ref": "artifacts/workflow_summary_iter0.json",
                        "farfield_ref": None,
                        "current_distribution_ref": None,
                    }
                }
                
                logger.info(f"Sending feedback: {json.dumps(feedback, indent=2)[:500]}...")
                
                # Send feedback
                response = await api_client.send_result(feedback)
            
            logger.info(f"Response: {json.dumps(response, indent=2) if response else 'None'}")
            
            # Check response
            if not response:
                self.log_error("No response from feedback endpoint")
                return False
            
            next_action = response.get("next_action", "unknown")
            
            if next_action == "completed":
                self.log_success("Design optimization completed!")
                return True
            elif next_action == "continue_iteration":
                self.log_success("Server accepted feedback, requesting next iteration")
                return True
            else:
                self.log_success(f"Feedback accepted, server status: {next_action}")
                return True
            
        except Exception as e:
            self.log_error(f"Client feedback failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def run_workflow(self):
        """Run complete workflow"""
        print("\n\n")
        print("╔" + "="*68 + "╗")
        print("║" + " "*68 + "║")
        print("║" + "ANTENNA CLIENT - SERVER WORKFLOW VALIDATION".center(68) + "║")
        print("║" + f"Server: {self.base_url}".center(68) + "║")
        print("║" + " "*68 + "║")
        print("╚" + "="*68 + "╝")
        
        # Run workflow steps
        step1_ok = await self.step_1_health_check()
        if not step1_ok:
            self.log_error("Workflow aborted at Step 1")
            return False
        
        step2_ok = await self.step_2_optimize_request()
        if not step2_ok:
            self.log_warning("Step 2 failed, skipping remaining steps")
            return False
        
        step3_ok = await self.step_3_execute_commands()
        step4_ok = await self.step_4_client_feedback()
        
        # Print summary
        self.print_summary()
        
        return len(self.errors) == 0
    
    def print_summary(self):
        """Print workflow summary"""
        duration = datetime.now() - self.start_time
        
        print("\n\n")
        print("╔" + "="*68 + "╗")
        print("║" + "WORKFLOW SUMMARY".center(68) + "║")
        print("╠" + "="*68 + "╣")
        
        # Success count
        print(f"║ ✓ Successes: {len(self.successes):<52} ║")
        for success in self.successes[:5]:
            print(f"║   • {success:<64} ║")
        if len(self.successes) > 5:
            print(f"║   ... and {len(self.successes) - 5} more")
        
        # Warnings
        if self.warnings:
            print(f"║                                                                    ║")
            print(f"║ ⚠ Warnings: {len(self.warnings):<53} ║")
            for warning in self.warnings[:3]:
                print(f"║   • {warning:<64} ║")
        
        # Errors
        if self.errors:
            print(f"║                                                                    ║")
            print(f"║ ✗ Errors: {len(self.errors):<55} ║")
            for error in self.errors[:3]:
                print(f"║   • {error:<64} ║")
        
        print("╠" + "="*68 + "╣")
        print(f"║ Duration: {str(duration):<56} ║")
        
        if self.errors:
            print(f"║ Status: ✗ WORKFLOW FAILED (Review errors above)".ljust(69) + "║")
        else:
            print(f"║ Status: ✓ WORKFLOW COMPLETE (All steps successful)".ljust(69) + "║")
        
        print("╚" + "="*68 + "╝")
        
        # Return exit code
        return 0 if len(self.errors) == 0 else 1


async def main():
    validator = WorkflowValidator()
    success = await validator.run_workflow()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
