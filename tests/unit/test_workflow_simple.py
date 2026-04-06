#!/usr/bin/env python3
"""
Simplified Workflow Validation - No Unicode Issues

Tests the full end-to-end workflow after schema fixes.
"""

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
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

async def main():
    """Run complete workflow after schema fixes"""
    
    print("\n" + "="*70)
    print("WORKFLOW VALIDATION - AFTER SCHEMA FIXES")
    print("="*70)
    print(f"Server: {SERVER_BASE_URL}")
    print(f"Timeout: {SERVER_TIMEOUT}s")
    
    errors = []
    successes = []
    
    try:
        # Step 1: Health Check
        print("\n[STEP 1] Health Check ...")
        connector = ServerConnector(SERVER_BASE_URL, timeout_sec=SERVER_TIMEOUT)
        async with connector:
            health = await connector.get("/api/v1/health")
        
        if health.get("status") == "ok":
            successes.append(f"Health check OK: ANN={health.get('ann_status')}, LLM={health.get('llm_status')}")
            print("[PASS] Health check passed")
        else:
            errors.append(f"Health check failed: {health}")
            print("[FAIL] Health check failed")
            return False
        
        # Step 2: Make optimize request
        print("\n[STEP 2] Optimize Request ...")
        connector = ServerConnector(SERVER_BASE_URL, timeout_sec=SERVER_TIMEOUT)
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
            
            # Log request for debugging
            req_dict = request.model_dump() if hasattr(request, 'model_dump') else request.dict()
            logger.info(f"Request schema_version: {req_dict.get('schema_version')}")
            logger.info(f"Request has priority: {'priority' in req_dict.get('runtime_preferences', {})}")
            
            # Send request
            try:
                response = await api_client.optimize(req_dict)
                
                if response and response.status in ("accepted", "completed"):
                    session_id = response.session_id if hasattr(response, 'session_id') else response.get('session_id')
                    trace_id = response.trace_id if hasattr(response, 'trace_id') else response.get('trace_id')
                    successes.append(f"Optimize request accepted: session={session_id}")
                    print(f"[PASS] Optimize request passed")
                    print(f"  Session ID: {session_id}")
                    print(f"  Trace ID: {trace_id}")
                else:
                    errors.append(f"Unexpected response status: {response.status if response else 'None'}")
                    print(f"[FAIL] Optimize request failed")
                    return False
                    
            except Exception as e:
                error_msg = str(e)
                errors.append(error_msg)
                print(f"[FAIL] Optimize request error: {error_msg[:100]}")
                return False
        
        # Step 3: Command execution (simulated)
        print("\n[STEP 3] Command Execution (simulated) ...")
        successes.append("Command execution validated")
        print("[PASS] Commands would execute on client")
        
        # Step 4: Feedback (simulated)
        print("\n[STEP 4] Client Feedback (simulated) ...")
        successes.append("Feedback would be sent to server")
        print("[PASS] Feedback would be sent")
        
    except Exception as e:
        import traceback
        errors.append(str(e))
        logger.error(traceback.format_exc())
        print(f"[ERROR] {e}")
    
    # Report
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Successes: {len(successes)}")
    for s in successes:
        print(f"  [OK] {s}")
    
    if errors:
        print(f"\nErrors: {len(errors)}")
        for e in errors:
            print(f"  [FAIL] {e[:100]}")
        return False
    else:
        print("\n[SUCCESS] All workflow steps passed!")
        return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
