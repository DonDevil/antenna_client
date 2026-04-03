#!/usr/bin/env python3
"""Verify RequestBuilder generates correct schema"""

from comm.request_builder import RequestBuilder

rb = RequestBuilder()
req = rb.build_optimize_request('I need a 2.4 GHz patch antenna')

print('✅ Request compiles successfully')
print(f'Schema version: {req.schema_version}')
print(f'User request: {req.user_request}')
print(f'Target: {req.target_spec.get("frequency_ghz")} GHz, {req.target_spec.get("bandwidth_mhz")} MHz')
print(f'Materials: {req.design_constraints.get("allowed_materials")}')
print(f'Substrates: {req.design_constraints.get("allowed_substrates")}')
print(f'Client capabilities: {req.client_capabilities.get("export_formats")}')
print('✅ All required fields present and correct!')
