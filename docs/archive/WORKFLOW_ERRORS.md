# Workflow Validation Errors Report

**Date**: April 6, 2026  
**Test**: End-to-End Workflow Validation  
**Result**: ❌ FAILED at Step 2  

---

## Workflow Steps

| Step | Task | Status |
|------|------|--------|
| 1 | GET /api/v1/health | ✅ PASS |
| 2 | POST /api/v1/optimize | ❌ FAIL (422 Unprocessable Entity) |
| 3 | Execute commands | ⏭️ SKIPPED |
| 4 | POST /api/v1/feedback | ⏭️ SKIPPED |

---

## Step 1: Health Check ✅

**Endpoint**: `GET /api/v1/health`  
**Status**: **PASS**

**Server Response**:
```json
{
  "status": "ok",
  "service": "AMC Antenna Optimization Server",
  "version": "0.1.0",
  "ann_status": "available",
  "ann_model_loaded": true,
  "llm_status": "available",
  "llm_model": "deepseek-r1:8b",
  "ollama_reachable": true
}
```

✅ Server is online and models are ready.

---

## Step 2: Optimize Request ❌

**Endpoint**: `POST /api/v1/optimize`  
**Status**: **FAIL**  
**Status Code**: 422 Unprocessable Entity  
**Error Code**: `SCHEMA_VALIDATION_FAILED`

### Server Validation Error

```json
{
  "error_code": "SCHEMA_VALIDATION_FAILED",
  "message": "<root>: 'schema_version' is a required property; <root>: 'target_spec' is a required property; <root>: 'design_constraints' is a required property; <root>: 'optimization_policy' is a required property; <root>: 'runtime_preferences' is a required property"
}
```

### Required Fields by Server

The server expects AT MINIMUM:
1. ✓ `schema_version` - Request schema version
2. ✓ `target_spec` - Design target specifications
3. ✓ `design_constraints` - Design constraints
4. ✓ `optimization_policy` - Optimization settings
5. ✓ `runtime_preferences` - Runtime preferences

### Client Request Format

**Client is sending**:
```json
{
  "schema_version": "optimize_request.v1",
  "user_request": "Design a microstrip patch antenna at 2.45 GHz with 100 MHz bandwidth",
  "target_spec": {
    "frequency_ghz": 2.45,
    "bandwidth_mhz": 100.0,
    "antenna_family": "microstrip_patch"
  },
  "design_constraints": {
    "allowed_materials": ["Copper (annealed)"],
    "allowed_substrates": ["Rogers RT/duroid 5880"]
  },
  "optimization_policy": {
    "mode": "auto_iterate",
    "max_iterations": 5,
    "stop_on_first_valid": true,
    "acceptance": {...}
  },
  "runtime_preferences": {...}
}
```

### Analysis

**What the client sends**: All 5 required fields present ✓  
**What server rejects**: Returns 422 anyway ✗

### Root Cause: DEEPLY NESTED REQUIRED FIELDS

**The server validates VERY STRICT nested field requirements:**

#### Phase Analysis Results:

**Phase 1** - Minimal request MISSING:
- `allowed_materials`, `allowed_substrates` (in design_constraints)
- `max_iterations`, `stop_on_first_valid` (in optimization_policy)

**Phase 2** - After adding target_spec STILL MISSING:
- `stop_on_first_valid`, `acceptance`, `fallback_behavior` (in optimization_policy)

**Phase 3** - After adding design_constraints STILL MISSING:
- `require_explanations`, `persist_artifacts` (in runtime_preferences)

**Phase 4** - After adding optimization_policy STILL MISSING:
- `llm_temperature`, `timeout_budget_sec` (in runtime_preferences)

**Phase 5** - After adding runtime_preferences STILL MISSING:
- `fallback_behavior` (in optimization_policy - recursively required!)
- `priority` (unknown location)
- `user_request` (top-level)

### Server's Actual Required Fields Structure:

```json
{
  "schema_version": "optimize_request.v1",
  "user_request": "string (REQUIRED)",
  "target_spec": {
    "frequency_ghz": number,
    "bandwidth_mhz": number,
    "antenna_family": string
  },
  "design_constraints": {
    "allowed_materials": ["string"],  // REQUIRED
    "allowed_substrates": ["string"]  // REQUIRED
  },
  "optimization_policy": {
    "mode": string,
    "max_iterations": number,        // REQUIRED
    "stop_on_first_valid": boolean,  // REQUIRED
    "acceptance": {...},             // REQUIRED
    "fallback_behavior": string      // REQUIRED (recursive!)
  },
  "runtime_preferences": {
    "require_explanations": boolean,  // REQUIRED
    "persist_artifacts": boolean,     // REQUIRED
    "llm_temperature": number,        // REQUIRED
    "timeout_budget_sec": number      // REQUIRED
  },
  "priority": string                  // REQUIRED (location unknown!)
}
```

### The Real Problem:

The server's validation is **RECURSIVELY checking fields** that the client builder doesn't set to the required values. Every nested object has its own set of mandatory fields, and they compound.

---

## Detailed Error Trace

```
Time: 2026-04-06 21:02:25.307
Attempt 1: 422 Error (Retry in 1.0s)
Attempt 2: 422 Error (Retry in 2.0s)
Attempt 3: 422 Error (FAILED)

Total Duration: ~3.3 seconds
Retry Logic: ✓ Working (exponential backoff applied)
```

---

## What Works vs What Fails

### ✅ Working

- Server connectivity: Online
- Health check: Passing
- Models: Loaded (ANN: available, LLM: available)
- Retry logic: Working
- Connection pooling: Working

### ❌ Failing

- Request schema validation on server side
- Optimize endpoint rejecting valid request format

---

## Recommended Next Steps

### For Client Team
1. **Get OpenAPI spec** from antenna_server team
   - Check exact field requirements for POST /api/v1/optimize
   - Verify nested field structures
   - Confirm field types and constraints

2. **Debug request body**
   - Print actual JSON being sent
   - Compare with server's expected schema
   - Check for field ordering issues

3. **Test with curl**
   ```bash
   curl -X POST http://192.168.29.147:8000/api/v1/optimize \
     -H "Content-Type: application/json" \
     -d @payload.json -v
   ```

### For Server Team
1. **Return detailed validation errors**
   - Include which field failed validation
   - Provide expected vs actual
   - Suggest corrections

2. **Verify Pydantic models**
   - Check OptimizeRequest model definition
   - Ensure all required fields are correct
   - Match with COMMUNICATION.md specification

3. **Share schema docs** with client team
   - OpenAPI/Swagger spec
   - Example valid requests
   - Field descriptions and constraints

---

## Comparison: Expected vs Actual

| Aspect | Expected (COMMUNICATION.md) | Actual (Server) |
|--------|---------------------------|-----------------|
| Endpoint | POST /api/v1/optimize | ✓ Match |
| Status Code | 200/201 | ✗ 422 |
| Response | command_package | ✗ Not reached |
| Error Handling | Yes | ✓ Graceful (422 is correct error for validation) |

---

## Verdict

**Issue Type**: Schema mismatch (client vs server expectations)  
**Severity**: High (blocks workflow)  
**Affected Step**: Step 2/4  
**Workflow Progress**: 25% (1/4 steps complete)

**Next Action**: Sync on request/response schemas with antenna_server team.

---

## Recovery Path

Once schemas are aligned:
1. ✓ Step 1: Health check (working)
2. ⏳ Step 2: Optimize request (fix schema)
3. ⏳ Step 3: Execute commands (test once #2 works)
4. ⏳ Step 4: Send feedback (test once #2 works)

Expected timeline: **1-2 hours** once server team confirms expected schemas.

---

**Generated**: 2026-04-06T21:02:28Z  
**Test Runner**: workflow_validation.py  
**Exit Code**: 1 (Failed)
