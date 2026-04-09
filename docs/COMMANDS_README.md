# Antenna Family Commands & Recipe Implementation

**Status**: Production-Ready Commands & Tests ✅

## What Was Created

### 1. **Command Definitions** (`src/comm/antenna_commands.py`)
- `RectPatchCommand` - Rectangular microstrip patch antenna parameters
- `AMCPatchCommand` - Artificial Magnetic Conductor array parameters  
- `WBANPatchCommand` - Wearable Body Area Network parameters
- `AntennaCommandFactory` - Factory for creating validated commands

**Key Features:**
- Pydantic-based validation for all parameters
- Type-safe command creation with sensible defaults
- Server-side calculation focus (client sends specs, server calculates geometry)
- Easy integration with existing request builder

### 2. **Command Recipe** (`docs/COMMAND_RECIPE.md`)
Complete workflow documentation with:
- 8-step command flow architecture (client ↔ server ↔ CST)
- Code examples for each family
- Parameter reference tables
- Error handling patterns
- Testing guidelines

### 3. **Complete Test Suite** (41 tests total)

#### Command Tests (21 tests in `test_antenna_commands.py`)
- Command creation and validation for each family
- Parameter range checking  
- Serialization to JSON
- Request building from commands
- Server response handling
- Full workflow simulation

#### CST Execution & Result Extraction (20 tests in `test_cst_execution_extraction.py`)
- VBA macro structure validation for rect patch, AMC, WBAN
- S11 data parsing and center frequency identification
- Bandwidth, return loss, VSWR, gain extraction
- Radiation efficiency and far-field metrics
- AMC array gain improvement calculation
- WBAN frequency shift and SAR extraction
- Complete metrics packages ready for feedback

#### API Tests (4 tests - existing, unchanged)
- ✅ All passing

**Total: 45/45 Tests Passing** ✅ No errors, no regressions

### 4. **Test Calculator Implementations** (`tests/calculators/`)
Moved from `src/tools/antenna_calculations/` to test directory:
- `rect_patch_calculator.py` - For validation during testing
- `amc_calculator.py` - For test implementation
- `wban_calculator.py` - For ANN training support

**NOTE**: These are for **testing only** until the ANN model is ready. Production calculations are done server-side.

---

## Quick Start

### Create and Send Commands

```python
from comm.antenna_commands import AntennaCommandFactory
from comm.request_builder import RequestBuilder

# 1. Create command
rect_cmd = AntennaCommandFactory.create_rect_patch_command(
    frequency_ghz=2.4,
    bandwidth_mhz=100.0
)

# 2. Build request
builder = RequestBuilder()
request = builder.build_optimize_request(
    user_text="Design antenna",
    design_specs=rect_cmd.dict()
)

# 3. Send to server
response = client.post("/api/v1/optimize", request.dict())
```

### Execute CST Simulations

```python
from cst_client.cst_app import CSTApp
from cst_client.vba_executor import VBAExecutor

cst = CSTApp()
executor = VBAExecutor(cst)

# Execute VBA macros from server response
executor.execute_macro(response["command_package"]["cst_vba_setup"])
executor.execute_macro(response["command_package"]["cst_vba_geometry"])

# Run simulation
cst.run_simulation()
```

### Extract Results

```python
from cst_client.result_extractor import ResultExtractor

extractor = ResultExtractor()
s11_data = extractor.extract_s11("results/S11.txt")
metrics = extractor.extract_metrics(s11_data)

feedback = {
    "session_id": response["session_id"],
    "actual_return_loss_db": metrics["return_loss_db"],
    "actual_efficiency": metrics["efficiency_percent"] / 100.0,
    "status": "achieved_convergence"
}

# Send feedback for ANN training
client.post("/api/v1/client-feedback", feedback)
```

---

## File Locations

### Client Code
- Commands: [src/comm/antenna_commands.py](src/comm/antenna_commands.py)
- Request Builder: [src/comm/request_builder.py](src/comm/request_builder.py)
- CST Execution: [src/cst_client/](src/cst_client/)
- Result Extraction: [src/cst_client/result_extractor.py](src/cst_client/result_extractor.py)

### Documentation
- Recipe: [docs/COMMAND_RECIPE.md](docs/COMMAND_RECIPE.md)
- API: [docs/API.md](docs/API.md)

### Testing
- Command Tests: [tests/unit/test_antenna_commands.py](tests/unit/test_antenna_commands.py)
- CST Tests: [tests/unit/test_cst_execution_extraction.py](tests/unit/test_cst_execution_extraction.py)
- Test Calculators: [tests/calculators/](tests/calculators/)

---

## Antenna Family Commands

### 1. Rectangular Microstrip Patch

```python
cmd = AntennaCommandFactory.create_rect_patch_command(
    frequency_ghz=2.4,
    bandwidth_mhz=100.0,
    patch_shape="rectangular",      # or "circular", "square"
    feed_type="edge",               # or "coaxial", "proximity-coupled"
    min_efficiency_percent=80.0,
    max_vswr=2.0
)
```

**Expected Results:**
- Length: ~29.44 mm (for 2.4 GHz on FR-4)
- Width: ~38.04 mm
- Gain: 5-7 dBi
- Return Loss: < -10 dB
- Efficiency: 80-95%

### 2. AMC Patch Array

```python
cmd = AntennaCommandFactory.create_amc_command(
    frequency_ghz=2.4,
    bandwidth_mhz=100.0,
    amc_unit_cell_count_per_side=7,  # 7x7 array
    amc_air_gap_preference="standard", # "minimal", "nominal", "spaced"
    min_gain_improvement_db=2.0
)
```

**Expected Results:**
- Unit Cell Period: ~28.12 mm
- Air Gap: ~7.5 mm
- Array Dimension: ~197 mm
- Gain Improvement: +2-3 dB
- Critical: AMC resonance ±3% of patch frequency

### 3. WBAN (On-Body)

```python
cmd = AntennaCommandFactory.create_wban_command(
    operating_frequency_ghz=2.4,      # On-body target
    body_proximity_mm=5.0,             # Distance from skin
    design_frequency_upshift_percent=5.0,  # Compensation
    sar_limit_w_per_kg_1g=1.6,         # FCC limit
    sar_limit_w_per_kg_10g=2.0
)
```

**Expected Results:**
- Design Frequency: ~2.52 GHz (upshifted)
- On-Body Resonance: 2.40 GHz (after body detuning)
- Gain On-Body: 2-6 dBi
- SAR: < 1.6 W/kg (1g average, FCC compliant)

---

## Integration Points

### Command → Request Builder
Automatic conversion to optimize request schema:
```python
request = builder.build_optimize_request(
    user_text="...",
    design_specs=command.dict()  # Seamless integration
)
```

### Server → CST Execution
Server returns command package with:
- `calculated_params`: Actual dimensions from server calculations
- `cst_vba_setup`: Material, substrate setup
- `cst_vba_geometry`: Patch, feed, AMC geometry
- `cst_vba_simulation`: Solver, ports configuration
- `cst_vba_export`: Result export configuration

### CST Results → Feedback
Extracted metrics sent back to server for ANN training:
```python
feedback = {
    "session_id": "...",
    "actual_return_loss_db": ...,
    "actual_efficiency": ...,
    "measured_center_frequency_ghz": ...,
    "status": "achieved_convergence"
}
```

---

## Testing Results

```
============================== 45 passed ==============================
✅ 21 command tests (validation, serialization, workflows)
✅ 20 CST/extraction tests (VBA, parsing, metrics)
✅ 4 API tests (requests, responses, parsing)
✅ Zero errors, zero regressions, zero warnings (Pydantic deprecations only)
```

---

## Next Steps

1. **ANN Development** - Use feedback data to train neural network
2. **Parameter Optimization** - ANN predictions accelerate iteration
3. **Hardware Validation** - Fabricate designs for measurements
4. **Extended Families** - Add more antenna types to command system
5. **Automation** - Integrate with design workflow automation

---

## Architecture Notes

### Design Philosophy
- **Client-side**: Domain orchestration, command building, result extraction
- **Server-side**: All calculations (geometry, predictions, responses)
- **CST**: Simulation validation, metric gathering
- **Feedback Loop**: Metrics → ANN training → Better predictions

### Why Command Objects?
- Type safety: Pydantic validation catches errors early
- Documentation: Parameter constraints codified
- Extensibility: New families just add new command classes
- Testing: Mock responses trivial with structured commands
- Versioning: Command schema evolution trackable

### Why Test Calculators?
- Unit testing: Validate calculation logic independently
- ANN training: Reference values before full optimization
- Regression detection: Comparison baseline for CST
- Not production: Server handles all real calculations

---

## Questions?

Refer to:
- **How to use**: [COMMAND_RECIPE.md](docs/COMMAND_RECIPE.md)
- **API Details**: [API.md](docs/API.md)
- **Testing**: [tests/unit/](tests/unit/)
- **Examples**: Test files contain working examples
