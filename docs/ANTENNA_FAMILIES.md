"""
# Antenna Family Implementations - Complete Guide

This document describes the three antenna family implementations with their design calculators, use cases, and integration patterns.

---

## 1. Rectangular Microstrip Patch Antenna

### Purpose
The rectangular microstrip patch is the simplest and most well-understood antenna topology. It provides a baseline for efficient, low-profile antenna design across a wide frequency range (0.5-100 GHz).

### Key Characteristics
- **Dimensions**: ~λ/2 length, ~λ for width (depending on bandwidth)
- **Feeding**: Edge-fed inset microstrip feed for impedance matching
- **Resonance**: TM10 fundamental mode
- **Gain**: Typical 5-7 dBi
- **Bandwidth**: Narrow (2-5% of center frequency)
- **Efficiency**: High (80-95%) on low-loss substrates

### Design Workflow
1. Select substrate (εr, height)
2. Calculate patch dimensions using transmission line equations
3. Determine feed offset for 50Ω matching
4. Validate with CST simulation
5. Tune dimensions if frequency error exceeds ±5%

### Calculator Usage

```python
from src.tools.antenna_calculations import RectangularPatchCalculator, SubstrateProperties

calc = RectangularPatchCalculator()
substrate = SubstrateProperties(epsilon_r=4.4, height_mm=1.6, tan_delta=0.019)

# Calculate dimensions at 2.4 GHz
dims = calc.calculate_dimensions(
    target_frequency_ghz=2.4,
    substrate=substrate,
    target_bandwidth_mhz=100.0
)

# Predict performance
perf = calc.predict_performance(
    target_frequency_ghz=2.4,
    dimensions=dims,
    substrate=substrate
)

print(f"Length: {dims.length_mm:.2f} mm")
print(f"Gain: {perf.gain_dbi:.1f} dBi")
print(f"Efficiency: {perf.efficiency_pct:.1f}%")
```

### Substrates Supported
- FR-4 (lossy, low cost)
- Rogers RT/duroid 5880 (low loss, premium)
- Rogers RO3003 (low loss, WBAN applications)

### Acceptance Criteria
- Return Loss: ≤ -10 dB (VSWR ≤ 2.0)
- Frequency Error: ±5% of target
- Efficiency: ≥ 60% (with real substrate losses)

---

## 2. Artificial Magnetic Conductor (AMC)

### Purpose
AMC provides a high-impedance surface to reflect electromagnetic energy with near-zero phase shift at resonance. Used to:
- Increase antenna gain (typically +2-3 dB)
- Suppress back radiation
- Reduce ground plane size
- Improve radiation efficiency

### Key Characteristics
- **Unit Cell Size**: 0.15-0.30 λ
- **Resonance**: Absorption or reflection depending on design
- **Reflection Phase**: 0° at resonance (±90° bandwidth typical)
- **Matching Condition**: f_AMC ≈ f_patch (±3% tolerance critical)
- **Array Size**: Minimum 3×3 to 10×10 cells
- **Spacing**: 2-8% wavelength gap from patch antenna

### Design Workflow
1. Calculate unit cell period from wavelength
2. Determine patch size (typically 60-90% of period)
3. Build array (enforce 3 × patch dimension minimum)
4. Calculate air gap distance for patch-AMC coupling
5. Verify frequency matching (patch ↔ AMC resonance)

### Calculator Usage

```python
from src.tools.antenna_calculations import AMCCalculator

amc_calc = AMCCalculator()

# Design unit cell at 2.4 GHz
unit_cell = amc_calc.calculate_unit_cell(
    target_frequency_ghz=2.4,
    substrate_height_mm=1.6,
    epsilon_r=4.4
)

# Build array (enforces minimum size constraints)
array = amc_calc.build_array(
    unit_cell=unit_cell,
    target_frequency_ghz=2.4,
    substrate_height_mm=1.6,
    epsilon_r=4.4
)

# Calculate air gap spacing
air_gap_mm = amc_calc.calculate_air_gap_distance(
    target_frequency_ghz=2.4,
    gap_type="nominal"  # "minimal", "nominal", or "maximal"
)

# Predict performance with patch antenna matching
perf = amc_calc.predict_performance(
    unit_cell=unit_cell,
    array=array,
    target_frequency_ghz=2.4,
    patch_frequency_ghz=2.4  # Patch resonance frequency
)

print(f"Unit Cell Period: {unit_cell.period_mm:.2f} mm")
print(f"Array Size: {array.rows}×{array.cols}")
print(f"Air Gap: {air_gap_mm:.2f} mm")
print(f"Gain Improvement: {perf.gain_improvement_db:.2f} dB")
print(f"Reflection Phase: {perf.reflection_phase_deg:.1f}°")
```

### Critical Design Rule
**Frequency Matching is ESSENTIAL**

The AMC resonant frequency MUST match the patch frequency:
- |f_AMC - f_patch| < 3% (typical tolerance)
- Mismatch causes impedance discontinuity and radiation pattern distortion
- Use reflection phase validation (-90° to +90° is acceptable bandwidth)

### Tuning Procedure
If AMC frequency doesn't match patch:

```python
# If too high, decrease period or patch size
# If too low, increase period or patch size

tuned_cell = amc_calc.tune_for_frequency(
    unit_cell=unit_cell,
    current_frequency_ghz=2.4,
    target_frequency_ghz=2.45  # New target
)
```

---

## 3. WBAN (Wearable Body Area Network) Antenna

### Purpose
WBAN antennas operate close to the human body (2-20mm distance), requiring special handling for:
- Body proximity detuning (2-8% frequency shift)
- Dynamic impedance changes
- SAR (Specific Absorption Rate) constraints
- Bending tolerance on curved surfaces

### Key Characteristics
- **Detuning**: 2-8% frequency shift when worn on body
- **Design Strategy**: Use design frequency 3-10% above target (compensation)
- **Ground Slot**: Added for bandwidth and body decoupling
- **SAR Limits**: 1.6 W/kg (1g), 2.0 W/kg (10g) per regulations
- **Feed Offset**: Variable for body-dependent impedance matching
- **Flexibility**: Must survive bending to ~30-50mm radius

### Design Workflow
1. Calculate design frequency with body detuning compensation
2. Generate patch dimensions at upshifted frequency
3. Add ground slot (20-50% of length, 8% of width)
4. Validate on-body performance
5. Check SAR compliance
6. Account for bending effects

### Calculator Usage

```python
from src.tools.antenna_calculations import WBANCalculator, BodyProperties

wban_calc = WBANCalculator()

# Define on-body conditions
body = BodyProperties(
    distance_mm=5.0,  # 5mm from skin
    bending_radius_mm=50.0,  # Arm radius ~50mm
    tissue_epsilon_r=40.0,  # Dielectric at 2.4 GHz
    tissue_sigma_s_m=1.5  # Conductivity S/m
)

# Calculate design frequency with compensation
design_freq = wban_calc.calculate_design_frequency(
    target_frequency_ghz=2.4,
    body_distance_mm=5.0,
    compensation_type="nominal"  # "minimal", "nominal", "maximal"
)
print(f"Design Frequency: {design_freq:.4f} GHz (compensation applied)")

# Calculate dimensions
dims = wban_calc.calculate_dimensions(
    design_frequency_ghz=design_freq,
    substrate_height_mm=1.6,
    epsilon_r=4.4,
    body_properties=body
)
print(f"Patch: {dims.length_mm:.2f}×{dims.width_mm:.2f} mm")
print(f"Ground Slot: {dims.ground_slot_length_mm:.2f}×{dims.ground_slot_width_mm:.2f} mm")

# Predict on-body performance
perf = wban_calc.predict_on_body_performance(
    design_frequency_ghz=design_freq,
    target_frequency_ghz=2.4,
    dimensions=dims,
    substrate_epsilon_r=4.4,
    body_properties=body,
    transmitted_power_dbm=0.0  # 1W @ 0 dBm
)

# Check safety and performance
print(f"Resonant Frequency (on-body): {perf.resonant_frequency_on_body_ghz:.4f} GHz")
print(f"Frequency Shift: {perf.frequency_shift_mhz:.1f} MHz ({perf.detuning_pct:.1f}%)")
print(f"SAR 1g: {perf.sar_1g_w_kg:.2f} W/kg")
print(f"SAR 10g: {perf.sar_10g_w_kg:.2f} W/kg")
print(f"Is Safe: {perf.is_safe()}")
print(f"Meets Targets: {perf.meets_performance_targets()}")

# Account for bending
bending = wban_calc.account_for_bending(
    dimensions=dims,
    bending_radius_mm=50.0
)
print(f"Frequency Shift Due to Bending: {bending['frequency_shift_pct']:.1f}%")
```

### Body Properties Guidance
- **Distance 2-5mm**: Close contact (e.g., textile), high detuning (~6-8%)
- **Distance 5-10mm**: Typical wearable (e.g., patch antenna), moderate detuning (~4-6%)
- **Distance 10-20mm**: Loose coupling (e.g., tag), low detuning (~2-3%)

### SAR Safety Certification
For regulatory compliance (FCC, ETSI, IC):
- Measure actual SAR in tissue phantoms or numerical simulation
- Validate at expected wearing positions
- Document compliance report

### Bending Tolerance
WBAN antennas must survive bending without significant performance loss:
- Typical bending radius: 30-100mm (depending on wearer)
- Frequency shift < 2% acceptable with compensation
- Check substrate and solder joint mechanical integrity

---

## 4. Integration with Request Builder

The three families are integrated into the request builder automatically:

```python
from src.comm.request_builder import RequestBuilder

builder = RequestBuilder()

# Router automatically selects family-based defaults
request = builder.build_optimize_request(
    user_text="Design a 2.4 GHz WBAN antenna",
    design_specs={
        "antenna_family": "wban_patch",  # Auto-detected from text
        "frequency_ghz": 2.4,
        # Other parameters...
    }
)

# Family-specific defaults applied:
# - wban_patch: patch_shape="auto", feed_type="auto", polarization="unspecified"
# - amc_patch: patch_shape="auto", feed_type="auto", polarization="unspecified"
# - microstrip_patch: patch_shape="rectangular", feed_type="edge", polarization="linear"
```

### Family-Specific Substrates
```python
FAMILY_DEFAULT_SUBSTRATES = {
    "amc_patch": ["FR-4 (lossy)"],
    "microstrip_patch": ["Rogers RT/duroid 5880"],
    "wban_patch": ["Rogers RO3003"],
}
```

---

## 5. Performance Validation

### Rectangular Patch
- Test frequency within ±2.5% of target
- Return loss ≤ -10 dB (VSWR ≤ 2.0)
- Gain match within ±1 dBi of prediction

### AMC Array
- Reflection phase within ±15° of 0° at target frequency
- Array dimensions comply with 3× rule
- Gain improvement ≥ 1.5 dB with good patch matching

### WBAN
- Frequency shift ≤ 5% when worn on body
- SAR meets regulatory limits
- Bending-induced frequency shift ≤ 2%

---

## 6. Testing Guide

See `tests/unit/test_antenna_calculators.py` for comprehensive test examples:

```bash
# Run all antenna calculator tests
python -m pytest tests/unit/test_antenna_calculators.py -v

# Run specific family tests
python -m pytest tests/unit/test_antenna_calculators.py::TestRectangularPatchCalculator -v
python -m pytest tests/unit/test_antenna_calculators.py::TestAMCCalculator -v
python -m pytest tests/unit/test_antenna_calculators.py::TestWBANCalculator -v
```

All calculators include validation, error handling, and realistic physical constraints.

---

## References

- **IEE 802.15.6 WBAN Standard**: Body Area Networks specifications
- **High Frequency Structure Simulator (HFSS)**: EM simulation baseline
- **CST Microwave Studio**: Used for server-side simulation validation
- Rectangular Patch Design: Balanis, "Antenna Theory: Analysis and Design"
- AMC Design: Sievenpiper et al., "3D Metallo-Dielectric Photonic Crystals"
- WBAN Design: Hall, Horne, "Antenna Designer Notes"

"""