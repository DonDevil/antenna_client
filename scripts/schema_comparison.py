#!/usr/bin/env python3
"""
Schema Comparison Tool

Identifies exactly which fields the server expects vs what client sends.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from comm.request_builder import RequestBuilder

# What server requires (from error message)
SERVER_REQUIRED = [
    "schema_version",
    "target_spec",
    "design_constraints",
    "optimization_policy",
    "runtime_preferences"
]

# What client builds
request_builder = RequestBuilder()
request = request_builder.build_optimize_request(
    user_text="Design a microstrip patch antenna at 2.45 GHz with 100 MHz bandwidth",
    design_specs={
        "frequency_ghz": 2.45,
        "bandwidth_mhz": 100.0,
        "antenna_family": "microstrip_patch"
    }
)

request_dict = request.model_dump() if hasattr(request, 'model_dump') else request.dict()

print("\n" + "="*70)
print("SERVER vs CLIENT SCHEMA COMPARISON")
print("="*70)

print("\n[1] Required Fields Check:")
print("-" * 70)
for field in SERVER_REQUIRED:
    present = field in request_dict
    status = "✓" if present else "✗"
    print(f"{status} {field:<30} {'Present' if present else 'MISSING'}")

print("\n[2] Client Request Structure:")
print("-" * 70)
print(json.dumps(request_dict, indent=2, default=str)[:1500] + "...")

print("\n[3] Field Analysis:")
print("-" * 70)

for field in SERVER_REQUIRED:
    if field in request_dict:
        value = request_dict[field]
        if isinstance(value, dict):
            subfields = list(value.keys())
            print(f"\n✓ {field}:")
            print(f"  Type: {type(value).__name__}")
            print(f"  Sub-fields: {', '.join(subfields[:5])}")
            if len(subfields) > 5:
                print(f"             ... and {len(subfields)-5} more")
        elif isinstance(value, (list, str)):
            print(f"\n✓ {field}:")
            print(f"  Type: {type(value).__name__}")
            print(f"  Value: {str(value)[:100]}...")
        else:
            print(f"\n✓ {field}:")
            print(f"  Type: {type(value).__name__}")
            print(f"  Value: {value}")

print("\n[4] Validation Result:")
print("-" * 70)
all_present = all(field in request_dict for field in SERVER_REQUIRED)
print(f"All required fields present: {all_present}")

if not all_present:
    missing = [f for f in SERVER_REQUIRED if f not in request_dict]
    print(f"Missing fields: {missing}")
else:
    print("Conclusion: Client request has all required fields!")
    print("Issue may be in nested field validation or field types.")

print("\n" + "="*70)
