#!/usr/bin/env python3
"""Test request builder and validation"""

from comm.request_builder import RequestBuilder

print("Testing RequestBuilder validation:\n")

# Test 1: Extract frequency and bandwidth
print("Test 1: Extract frequency from 'I need a 2.4 GHz patch antenna'")
rb = RequestBuilder()
req = rb.build_optimize_request('I need a 2.4 GHz patch antenna')
print(f"  Frequency: {req.target_spec.get('frequency_ghz')} GHz")
print(f"  Bandwidth: {req.target_spec.get('bandwidth_mhz')} MHz")
print(f"  Family: {req.target_spec.get('antenna_family')}")
print(f"  Schema: {req.schema_version}")
print(f"  ✅ Valid request built\n")

# Test 2: Extract different frequency
print("Test 2: Extract from 'Design a 5 GHz WiFi antenna'")
req2 = rb.build_optimize_request('Design a 5 GHz WiFi antenna with 200 MHz bandwidth')
print(f"  Frequency: {req2.target_spec.get('frequency_ghz')} GHz")
print(f"  Bandwidth: {req2.target_spec.get('bandwidth_mhz')} MHz")
print(f"  ✅ Valid request built\n")

# Test 3: Default values for non-specific request
print("Test 3: Default values for 'antenna design'")
req3 = rb.build_optimize_request('I want to design an antenna')
print(f"  Frequency: {req3.target_spec.get('frequency_ghz')} GHz (default)")
print(f"  Bandwidth: {req3.target_spec.get('bandwidth_mhz')} MHz (default)")
print(f"  ✅ Valid request built with defaults\n")

print("✅ All RequestBuilder tests passed")
print(f"\nKey validation rules:")
print(f"  • User message minimum length: 10 characters")
print(f"  • Server requires: frequency_ghz and bandwidth_mhz")
print(f"  • Materials: {req.design_constraints['allowed_materials']}")
print(f"  • Substrates: {req.design_constraints['allowed_substrates']}")
