# WBAN (Wearable Body Area Network) Patch Antenna Design Rules - ADVANCED VERSION

---

## 1. Overview

WBAN antennas are wearable antennas designed to operate close to or on the human body.

Key challenges:
- Human body causes detuning
- High dielectric loading
- Increased losses
- SAR (safety constraint)

Typical use cases:
- Healthcare monitoring
- IoT wearable devices

---

## 2. Core Design Strategy

IMPORTANT:

Design frequency must be HIGHER than target frequency.

f_design = f_target * (1.03 to 1.10)

Reason:
- Body proximity shifts frequency downward

---

## 3. Base Geometry (Derived from Rectangular Patch)

Use standard patch equations:

lambda0 = c / f_design

W = c / (2 * f_design * sqrt((er + 1)/2))

eeff = (er + 1)/2 + (er - 1)/2 * (1 + 12*h/W)^(-0.5)

dL = 0.412*h * ((eeff + 0.3)*(W/h + 0.264)) / ((eeff - 0.258)*(W/h + 0.8))

Leff = c / (2 * f_design * sqrt(eeff))

L = Leff - 2*dL

---

## 4. Feed Design

Wf ≈ (0.03 to 0.08) * lambda0

feed_offset_y = (0.25 to 0.45) * L  
feed_offset_x = W / 2

---

## 5. WBAN-Specific Parameters

### Body Distance (CRITICAL)

body_distance = 2 mm to 10 mm

Effects:
- Smaller → more detuning, higher SAR
- Larger → better efficiency

---

### Bending Radius

bending_radius = 30 mm to 100 mm

Effects:
- Smaller radius → more deformation → frequency shift

---

## 6. Ground Modification (Bandwidth + Isolation)

### Ground Slot

slot_length = (0.2 to 0.5) * L  
slot_width  = (0.02 to 0.1) * W  

Used for:
- Bandwidth improvement
- Current redistribution

---

## 7. Human Body Effects

### Detuning

f_actual = f_design - (2% to 8%)

---

### Efficiency Reduction

eff_body = 40% to 80% of free-space efficiency

---

### SAR Approximation

SAR ∝ Power / (density * body_distance^2)

Implications:
- Decreasing body distance increases SAR
- Higher frequency increases SAR

---

## 8. Performance Metrics

### Return Loss
Target: < -10 dB

### VSWR
Target: < 2

### Gain
- On-body: 2–6 dBi
- Off-body: higher

### SAR
- 1g: < 1.6 W/kg
- 10g: < 2 W/kg

---

## 9. CST Simulation Setup

1. Create antenna structure
2. Add human body model (phantom)
3. Define body distance
4. Assign lossy tissue properties
5. Run simulation
6. Extract:
   - S11
   - Gain
   - SAR
   - Efficiency

---

## 10. Optimization Loop

### Step 1: Simulate

### Step 2: Evaluate

freq_error = actual - target

---

### Step 3: Fix Issues

| Problem | Fix |
|--------|-----|
| freq too high | increase L |
| freq too low | decrease L |
| high SAR | increase body_distance |
| low efficiency | increase ground size |
| detuning | adjust design frequency |

---

### Step 4: Iterate

---

## 11. Dataset Generation

### Inputs

- target_frequency
- substrate properties
- body_distance
- bending_radius

---

### Outputs

- patch geometry
- feed parameters
- slot dimensions

---

### Noise

param = ideal * (1 ± 5%)

---

### Labels

- actual_frequency
- return_loss
- vswr
- gain_on_body
- gain_off_body
- SAR
- efficiency_on_body

---

## 12. Acceptance Criteria

accepted = (
 abs(actual_frequency - target_frequency) < 5%
 AND vswr < 2
 AND return_loss < -10
 AND SAR < limit
)

---

## 13. Copilot Focus Rules (STRICT)

Copilot MUST:

1. Apply frequency compensation (f_design > f_target)
2. Include body distance in design
3. Consider SAR constraints
4. Adjust geometry for detuning
5. Use realistic human body effects

Copilot MUST NOT:

- design like free-space antenna
- ignore SAR
- ignore detuning
- assume ideal conditions

---

## 14. Integration Notes

### With Patch ANN
- Use patch equations as base

### With AMC
- Rare but possible
- Ensure isolation layer between AMC and body

---

## 15. Implementation Pipeline

1. Input target specs
2. Apply frequency compensation
3. Generate geometry
4. Add body model
5. Simulate
6. Extract results
7. Store dataset
8. Train ANN

---

## END
