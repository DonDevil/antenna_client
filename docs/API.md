# API

## Server Endpoints

- `GET /api/v1/health`: connectivity and service readiness.
- `GET /api/v1/capabilities`: server-supported antenna families and limits.
- `POST /api/v1/optimize`: submit a design request and receive an optimization response with command package.
- `POST /api/v1/client-feedback`: return execution feedback and refinement status.

## Antenna Families

The server supports three antenna family implementations with distinct design characteristics:

### 1. **Rectangular Microstrip Patch** (`microstrip_patch`)
- Recommended for: High-efficiency directive designs, standard frequency bands
- Default qualifiers: `patch_shape=rectangular, feed_type=edge, polarization=linear`
- Gain: 5-7 dBi typical
- Bandwidth: 2-5% (narrow-band)
- Efficiency: 80-95% (substrate-dependent)

### 2. **Artificial Magnetic Conductor** (`amc_patch`)
- Recommended for: Gain enhancement (+2-3 dB), back lobe suppression
- Default qualifiers: `patch_shape=auto, feed_type=auto, polarization=unspecified`
- Performance: +2-3 dB gain improvement over bare patch
- Critical constraint: AMC resonance frequency MUST match patch (±3% tolerance)

### 3. **WBAN (Wearable Body Area Network)** (`wban_patch`)
- Recommended for: On-body wearable applications, healthcare monitoring
- Default qualifiers: `patch_shape=auto, feed_type=auto, polarization=unspecified`
- Design approach: Upshift frequency 3-10% to compensate for body detuning
- Safety: SAR compliance checked (FCC/ETSI regulatory limits)

## Optimize Request Shape

The client builds requests in `comm.request_builder` with these high-level sections:

- `schema_version`
- `user_request`
- `target_spec`
- `design_constraints`
- `optimization_policy`
- `runtime_preferences`
- `client_capabilities`

### Target Spec by Family

**Rectangular Microstrip** (optimized for standard WI-FI/BLE):
```json
{
  "antenna_family": "microstrip_patch",
  "frequency_ghz": 2.4,
  "bandwidth_mhz": 100.0,
  "patch_shape": "rectangular",
  "feed_type": "edge",
  "polarization": "linear"
}
```

**AMC Array** (for high-gain directive design):
```json
{
  "antenna_family": "amc_patch",
  "frequency_ghz": 2.4,
  "bandwidth_mhz": 100.0,
  "patch_shape": "auto",
  "feed_type": "auto",
  "polarization": "unspecified"
}
```

**WBAN** (for on-body wearable):
```json
{
  "antenna_family": "wban_patch",
  "frequency_ghz": 2.4,
  "bandwidth_mhz": 100.0,
  "patch_shape": "auto",
  "feed_type": "auto",
  "polarization": "unspecified"
}
```

Required runtime preferences include:

- `require_explanations`
- `persist_artifacts`
- `llm_temperature`
- `timeout_budget_sec`
- `priority`

## Workflow

1. Check health.
2. Submit optimize request with appropriate family.
3. Execute returned CST command package.
4. Send client feedback.
5. Continue until the server returns completed status or a stop condition.

### Feedback Requirements

**Return Loss Convention**:
- `actual_return_loss_db` should be sent as the measured dB value, negative for matched designs.
- Example: -15 dB (good match), not +15 dB

**Far-Field Metrics** (when available from CST exports):
- `actual_efficiency`: Radiation efficiency (0.0-1.0 or 0-100% scale)
- `actual_front_to_back_db`: Front-to-back ratio in dB
- These are optional but improve ANN training quality

**Example Feedback Payload**:
```json
{
  "session_id": "abc-123",
  "actual_return_loss_db": -12.5,
  "actual_efficiency": 0.85,
  "actual_front_to_back_db": 18.5,
  "status": "achieved_convergence"
}
```

## Design Constraints and Acceptance

Each family enforces physical constraints:

### Rectangular Microstrip
- Frequency window: ±5% of target
- Return loss minimum: -10 dB (VSWR ≤ 2.0)
- Efficiency minimum: ≥60% (with realistic substrate losses)

### AMC
- Frequency matching: |f_AMC - f_patch| ≤ 3%
- Reflection phase: -90° to +90° (bandwidth constraint)
- Gain improvement: ≥ 1.5 dB

### WBAN
- On-body frequency: Within ±5% of target (after detuning compensation)
- SAR safety: ≤ 1.6 W/kg (1g), ≤ 2 W/kg (10g)
- Detuning: ≤ 8% acceptable with compensation

## Performance Metrics

### All Families Report
- Resonant frequency (with and without body for WBAN)
- Return loss / VSWR
- Gain (dBi)
- Radiation efficiency (%)
- Bandwidth (MHz)

### WBAN-Specific Metrics
- Frequency shift due to body proximity (MHz and %)
- SAR 1g and 10g averaged (W/kg)
- On-body vs off-body gain comparison

### AMC-Specific Metrics
- Reflection phase (degrees)
- Gain improvement (dB)
- Back lobe reduction (dB)