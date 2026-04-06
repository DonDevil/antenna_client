#!/usr/bin/env python3
"""
Deep Schema Validation Debug

Tests different combinations to find which nested field is failing.
"""

import asyncio
import json
import httpx
from pathlib import Path

SERVER_URL = "http://192.168.29.147:8000"

async def test_request(description: str, payload: dict) -> bool:
    """Test a request payload"""
    print(f"\n{'='*70}")
    print(f"TEST: {description}")
    print(f"{'='*70}")
    print(f"Payload: {json.dumps(payload, indent=2)[:300]}...")
    
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{SERVER_URL}/api/v1/optimize",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
        
        if response.status_code == 422:
            detail = response.json().get("detail", {})
            msg = detail.get("message", "Unknown error")
            # Extract meaningful error
            if "required property" in msg:
                # Extract which field
                import re
                fields = re.findall(r"'(\w+)' is a required property", msg)
                print(f"[FAIL] Missing required: {fields}")
            else:
                print(f"[FAIL] (422): {msg[:100]}")
            return False
        elif response.status_code in [200, 201]:
            print(f"[OK] SUCCESS (Status {response.status_code})")
            return True  
        else:
            print(f"[ERROR] Status {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"[ERROR] EXCEPTION: {e}")
        return False

async def main():
    """Run validation tests"""
    
    # Test 1: Minimal valid request
    print("\nPhase 1: MINIMAL PAYLOAD TEST")
    await test_request(
        "Minimal - Just required fields",
        {
            "schema_version": "optimize_request.v1",
            "target_spec": {
                "frequency_ghz": 2.45,
                "antenna_family": "microstrip_patch"
            },
            "design_constraints": {},
            "optimization_policy": {"mode": "auto"},
            "runtime_preferences": {}
        }
    )
    
    # Test 2: Add target_spec details
    print("\n\nPhase 2: ADD TARGET_SPEC")
    await test_request(
        "With full target_spec",
        {
            "schema_version": "optimize_request.v1",
            "target_spec": {
                "frequency_ghz": 2.45,
                "bandwidth_mhz": 100.0,
                "antenna_family": "microstrip_patch"
            },
            "design_constraints": {},
            "optimization_policy": {"mode": "auto_iterate", "max_iterations": 5},
            "runtime_preferences": {}
        }
    )
    
    # Test 3: Add design_constraints
    print("\n\nPhase 3: ADD DESIGN_CONSTRAINTS")
    await test_request(
        "With design_constraints",
        {
            "schema_version": "optimize_request.v1",
            "target_spec": {
                "frequency_ghz": 2.45,
                "bandwidth_mhz": 100.0,
                "antenna_family": "microstrip_patch"
            },
            "design_constraints": {
                "allowed_materials": ["Copper (annealed)"],
                "allowed_substrates": ["FR-4 (lossy)"]
            },
            "optimization_policy": {"mode": "auto_iterate", "max_iterations": 5},
            "runtime_preferences": {}
        }
    )
    
    # Test 4: Add optimization_policy details
    print("\n\nPhase 4: ADD OPTIMIZATION_POLICY")
    await test_request(
        "With full optimization_policy",
        {
            "schema_version": "optimize_request.v1",
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
                    "center_tolerance_mhz": 20,
                    "minimum_bandwidth_mhz": 80.0,
                    "maximum_vswr": 2.0
                }
            },
            "runtime_preferences": {}
        }
    )
    
    # Test 5: Add runtime_preferences
    print("\n\nPhase 5: ADD RUNTIME_PREFERENCES")
    await test_request(
        "With runtime_preferences",
        {
            "schema_version": "optimize_request.v1",
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
                    "center_tolerance_mhz": 20,
                    "minimum_bandwidth_mhz": 80.0,
                    "maximum_vswr": 2.0
                }
            },
            "runtime_preferences": {
                "require_explanations": False,
                "persist_artifacts": True
            }
        }
    )

if __name__ == "__main__":
    asyncio.run(main())
