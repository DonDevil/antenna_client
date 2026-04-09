# Command Recipe - Antenna Family Workflow

## Overview

This recipe describes the workflow for requesting antenna family optimizations from the server. The client sends command requests, receives CST execution instructions, executes them, and returns results.

**Design Principle**: Server performs all calculations; client manages orchestration and result extraction.

---

## Command Flow Architecture

```
Client                                Server                              CST Studio
  |                                      |                                    |
  |-- 1. Build Command Request -------->|                                    |
  |                                      |-- 2. Calculate Geometry ---------->|
  |                                      |   (VBA/Python backend)            |
  |                                      |<-- 3. Return CST Macro Package ---|
  |<-- 4. Receive Command Package -------|                                    |
  |                                      |                                    |
  |-- 5. Execute CST Macro ----------->| (CST Automation API)               |
  |<-- 6. Simulation Results ----------|                                    |
  |                                      |                                    |
  |-- 7. Send Feedback with Results -->|                                    |
  |                                      |-- 8. Update ANN Training          |
  |                                      |                                    |
```

---

## Step 1: Build Command Request

Create antenna command and convert to optimization request:

### Rectangular Microstrip Patch

```python
from comm.antenna_commands import AntennaCommandFactory
from comm.request_builder import RequestBuilder

# Create command
cmd = AntennaCommandFactory.create_rect_patch_command(
    frequency_ghz=2.4,
    bandwidth_mhz=100.0,
    patch_shape="rectangular",
    feed_type="edge",
    min_efficiency_percent=80.0
)

# Convert to request
builder = RequestBuilder()
optimize_req = builder.build_optimize_request(
    user_text="Design rectangular patch antenna at 2.4 GHz",
    design_specs=cmd.dict()
)

# Send to server
response = client.post("/api/v1/optimize", optimize_req.dict())
```

### AMC Patch Array

```python
# Create AMC command
cmd = AntennaCommandFactory.create_amc_command(
    frequency_ghz=2.4,
    bandwidth_mhz=100.0,
    amc_unit_cell_count_per_side=7,
    amc_air_gap_preference="standard",
    min_gain_improvement_db=2.0
)

# Send to server
optimize_req = builder.build_optimize_request(
    user_text="Design AMC array for high-gain 2.4 GHz antenna",
    design_specs=cmd.dict()
)

response = client.post("/api/v1/optimize", optimize_req.dict())
```

### WBAN On-Body Antenna

```python
# Create WBAN command
cmd = AntennaCommandFactory.create_wban_command(
    operating_frequency_ghz=2.4,
    bandwidth_mhz=100.0,
    body_proximity_mm=5.0,
    design_frequency_upshift_percent=5.0
)

optimize_req = builder.build_optimize_request(
    user_text="Design on-body WBAN antenna at 2.4 GHz",
    design_specs=cmd.dict()
)

response = client.post("/api/v1/optimize", optimize_req.dict())
```

---

## Step 2-3: Server Calculates & Returns CST Commands

Server processes request:
1. Calls antenna family calculator (Python backend)
2. Computes dimensions (patch length/width, feed position, AMC period, etc.)
3. Returns CST command package with VBA macros

**Response includes**:
- Calculated geometry parameters
- CST setup macros (material, simulation bounds, mesh)
- Design parameters VBA script
- Export configuration

Example response:

```json
{
  "status": "ready_for_execution",
  "command_package": {
    "family": "microstrip_patch",
    "calculated_params": {
      "patch_length_mm": 29.44,
      "patch_width_mm": 38.04,
      "feed_x_offset_mm": 0.0,
      "feed_y_offset_mm": 14.22,
      "substrate_epsilon_r": 2.2,
      "substrate_thickness_mm": 1.575
    },
    "cst_vba_setup": "Material.Reset\nMaterial.Name \"FR-4\"\n...",
    "cst_vba_geometry": "Rectangle.Reset\nRectangle.Name \"Patch\"\n...",
    "cst_vba_simulation": "Port.Reset\nPort.PortNumber 1\n...",
    "cst_vba_export": "SelectTreeItem(\"Farfield\", \"Realized Gain 2.4 GHz\")\n..."
  },
  "session_id": "abc-123-def"
}
```

---

## Step 4-5: Client Executes CST Commands

Load and execute CST macros in sequence:

```python
from cst_client.cst_app import CSTApp
from cst_client.vba_executor import VBAExecutor

# Connect to CST
cst = CSTApp()
cst.open_project("antenna_design.cst")

# Get executor
executor = VBAExecutor(cst)

# Execute setup macros in order
executor.execute_macro(response["command_package"]["cst_vba_setup"])
executor.execute_macro(response["command_package"]["cst_vba_geometry"])
executor.execute_macro(response["command_package"]["cst_vba_simulation"])

# Run simulation
cst.run_simulation()

# Export results
executor.execute_macro(response["command_package"]["cst_vba_export"])
```

---

## Step 6: Extract Simulation Results

Parse exported CST files to get metrics:

```python
from cst_client.result_extractor import ResultExtractor

extractor = ResultExtractor()

# Load exported S11 data
s11_data = extractor.extract_s11("proj_name/Results/S-Parameters/S11.txt")

# Extract key metrics
metrics = extractor.extract_metrics(s11_data)

# Example metrics for 2.4 GHz rect patch:
# {
#   "center_frequency_ghz": 2.401,
#   "bandwidth_mhz": 92.0,
#   "return_loss_db": -15.2,
#   "vswr": 1.36,
#   "gain_dbi": 6.1,
#   "efficiency_percent": 84.5,
#   "front_to_back_db": 12.3
# }
```

---

## Step 7: Send Client Feedback

Return measured results to server for ANN training:

```python
feedback = {
    "session_id": response["session_id"],
    "actual_return_loss_db": metrics["return_loss_db"],
    "actual_efficiency": metrics["efficiency_percent"] / 100.0,
    "actual_front_to_back_db": metrics.get("front_to_back_db"),
    "measured_center_frequency_ghz": metrics["center_frequency_ghz"],
    "status": "achieved_convergence"
}

# Send feedback
client.post("/api/v1/client-feedback", feedback)
```

---

## Command Parameters Reference

### Rectangular Microstrip Patch

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `frequency_ghz` | - | 0.1-100 | Target frequency |
| `bandwidth_mhz` | 100 | 10-5000 | Required bandwidth |
| `patch_shape` | rectangular | rectangular, circular, square | Patch shape |
| `feed_type` | edge | edge, coaxial, proximity-coupled | Feed method |
| `polarization` | linear | linear, circular | Polarization |
| `min_efficiency_percent` | 80 | 50-100 | Minimum efficiency target |
| `max_vswr` | 2.0 | 1.0-5.0 | Maximum VSWR |

### AMC Patch

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `frequency_ghz` | - | 0.1-100 | Target frequency |
| `amc_unit_cell_count_per_side` | 7 | 3-15 | Array size (N×N) |
| `amc_air_gap_preference` | standard | standard, tight, spaced | Air gap size |
| `min_gain_improvement_db` | 1.5 | 0.5-5 | Min gain improvement |
| `amc_frequency_tolerance_percent` | 3.0 | 0.5-10 | Frequency mismatch tolerance |

### WBAN

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `operating_frequency_ghz` | - | 0.1-100 | On-body frequency |
| `body_proximity_mm` | 5.0 | 0-30 | Distance from skin |
| `design_frequency_upshift_percent` | 5.0 | 3-10 | Compensation upshift |
| `sar_limit_w_per_kg_1g` | 1.6 | 0.1-2.0 | SAR limit (1g) |
| `sar_limit_w_per_kg_10g` | 2.0 | 0.1-10 | SAR limit (10g) |

---

## Integration with Request Builder

Commands are automatically converted to optimize requests:

```python
# The RequestBuilder recognizes antenna commands
request = builder.build_optimize_request(
    user_text="Design antenna",
    design_specs={
        "antenna_family": "microstrip_patch",
        "frequency_ghz": 2.4,
        "bandwidth_mhz": 100.0
    }
)

# Validates against schema and adds required fields:
# - schema_version
# - design_constraints  
# - optimization_policy
# - runtime_preferences
# - client_capabilities
```

---

## Error Handling

### Invalid Command

```python
try:
    cmd = AntennaCommandFactory.create_rect_patch_command(
        frequency_ghz=0.05  # Below minimum
    )
except ValueError as e:
    # "ensure this value is greater than 0.1" (Pydantic validation)
    handle_error(e)
```

### Server Calculation Failure

```python
response = client.post("/api/v1/optimize", request)
if response["status"] == "failed":
    # Server could not calculate geometry
    # Check: is frequency too high? Array too large? Constraints impossible?
    msg = response.get("error", "Unknown error")
    handle_error(msg)
```

### CST Execution Failure

```python
try:
    executor.execute_macro(vba_code)
except Exception as e:
    # CST not running, automation API error, macro syntax error
    handle_error(f"CST execution failed: {e}")
```

---

## Testing the Recipe

Unit tests verify each step:

```python
# tests/unit/test_antenna_commands.py
def test_rect_patch_command():
    cmd = AntennaCommandFactory.create_rect_patch_command(frequency_ghz=2.4)
    assert cmd.frequency_ghz == 2.4
    assert cmd.antenna_family == "microstrip_patch"

# tests/unit/test_cst_command_execution.py
def test_cst_rect_patch_execution():
    # Test VBA macro generation and execution
    # Verify CST project is created with correct geometry
    pass

# tests/unit/test_result_extraction.py
def test_extract_s11_metrics():
    # Test parsing of S11 results
    # Verify metrics extraction from CST exports
    pass
```

---

## Next Steps

1. **ANN Implementation**: Train neural network with collected feedback
2. **Parameter Optimization**: Use ANN predictions to reduce iteration cycles
3. **Multi-Family Support**: Extend to WBAN family optimization
4. **Hardware Validation**: Compare CST simulations with fabricated antennas
