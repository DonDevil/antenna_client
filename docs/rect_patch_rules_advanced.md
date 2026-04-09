# Rectangular Microstrip Patch Antenna Design Rules - ADVANCED VERSION

---

## 1. Overview

A rectangular microstrip patch antenna is a planar resonant radiator operating in TM10 mode.

Structure:
- Patch (radiator)
- Dielectric substrate
- Ground plane

Key behavior:
- Length (L) controls resonance
- Width (W) controls radiation efficiency and bandwidth

---

## 2. Core Design Workflow

1. Define target frequency (f0)
2. Select substrate (εr, h, tanδ)
3. Compute W, εeff, ΔL, L
4. Design feed (Wf, offset)
5. Define substrate/ground size
6. Simulate (CST)
7. Tune parameters

---

## 3. Fundamental Equations

c = 3e8

lambda0 = c / f0

W = c / (2 * f0 * sqrt((er + 1)/2))

eeff = (er + 1)/2 + (er - 1)/2 * (1 + 12*h/W)^(-0.5)

dL = 0.412*h * ((eeff + 0.3)*(W/h + 0.264)) / ((eeff - 0.258)*(W/h + 0.8))

Leff = c / (2 * f0 * sqrt(eeff))

L = Leff - 2*dL

---

## 4. Feed Design (Impedance Matching)

### Microstrip Feed Width (50Ω approx)

Wf ≈ (0.03 to 0.08) * lambda0

---

### Inset Feed Position

feed_offset_y = (0.2 to 0.4) * L  
feed_offset_x = W / 2

Behavior:
- Move toward center → lower impedance
- Move toward edge → higher impedance

---

## 5. Substrate and Ground

substrate_length = L + 6*h  
substrate_width  = W + 6*h  

Ground = same as substrate

---

## 6. Advanced Parameter Relationships

| Parameter | Effect |
|----------|--------|
| ↑ εr | ↓ size, ↓ bandwidth |
| ↑ h | ↑ bandwidth, ↓ efficiency |
| ↑ W | ↑ gain, ↑ bandwidth |
| ↑ L | ↓ resonant frequency |
| ↑ tanδ | ↓ efficiency |

---

## 7. Performance Metrics

### Return Loss (S11)
- Target: < -10 dB

### VSWR
- Target: < 2

### Gain
- Typical: 5–9 dBi

### Bandwidth
- Depends on h and εr

### Radiation Efficiency
- Affected by dielectric and conductor loss

### Directivity
- Function of radiation pattern

---

## 8. CST Simulation Setup

1. Create substrate (εr, h)
2. Create ground plane
3. Create patch (L, W)
4. Add feed line
5. Define port (waveguide or discrete)
6. Set frequency range (f0 ± 20%)
7. Mesh refinement
8. Run solver

---

## 9. Optimization Loop (CLOSED-LOOP)

### Step 1: Simulate

Extract:
- S11
- Resonant frequency
- Gain

---

### Step 2: Evaluate Errors

freq_error = actual - target

---

### Step 3: Apply Corrections

| Problem | Fix |
|--------|-----|
| freq too high | increase L |
| freq too low | decrease L |
| poor matching | adjust feed_offset_y |
| low bandwidth | increase h |
| low gain | increase W |

---

### Step 4: Iterate until convergence

---

## 10. Dataset Generation (Advanced)

### Inputs

- target_frequency
- εr
- h
- constraints

---

### Outputs

- L
- W
- feed geometry
- substrate size

---

### Noise Injection

param = ideal * (1 ± 5%)

---

### Labels

- actual_frequency
- return_loss
- vswr
- gain
- efficiency

---

## 11. Acceptance Criteria

accepted = (
 abs(actual_frequency - target_frequency) < 5%
 AND vswr < 2
 AND return_loss < -10
)

---

## 12. Copilot Focus Rules (STRICT)

Copilot MUST:

1. Compute lambda0 first
2. Use equations (not random values)
3. Maintain unit consistency
4. Respect scaling with frequency
5. Tune L for frequency correction
6. Tune feed for impedance

Copilot MUST NOT:

- assign arbitrary dimensions
- ignore dielectric effects
- skip simulation validation

---

## 13. Integration with Other Systems

### With AMC:
- Patch frequency must match AMC resonance

### With WBAN:
- Add detuning compensation (+3–10%)

---

## 14. Implementation Pipeline

1. Input target specs
2. Compute geometry
3. Export to CST
4. Simulate
5. Extract results
6. Log dataset
7. Train ANN

---

## END
