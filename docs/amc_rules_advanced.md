# AMC (Artificial Magnetic Conductor) Design Rules - ADVANCED VERSION

---

## 1. Overview

AMC is a periodic electromagnetic surface that behaves like a magnetic conductor at resonance.

Key property:
- Reflection phase ≈ 0° at resonance frequency

Used to:
- Increase gain
- Suppress back radiation
- Improve efficiency

---

## 2. Critical Matching Condition

f_amc ≈ f_patch

Tolerance:
|f_amc - f_patch| < 2–3%

This is the MOST IMPORTANT constraint.

---

## 3. Unit Cell Design (Physics + Geometry)

### Step 1: Define Frequency

f0 = target_frequency  
lambda0 = c / f0  

---

### Step 2: Substrate Selection

epsilon_r = 2.2 to 4.5  
h = (0.02 to 0.06) * lambda0  

---

### Step 3: Unit Cell Period

p = (0.15 to 0.30) * lambda0  

---

### Step 4: Patch Size

a = (0.6 to 0.9) * p  

---

### Step 5: Gap

g = p - a  

---

## 4. LC Model Understanding

f0 = 1 / (2π√LC)

Where:
- C ↑ when gap ↓ or patch ↑
- L ↑ when substrate thickness ↑

Tuning rules:
- Increase a → frequency ↓
- Increase g → frequency ↑
- Increase h → frequency ↓

---

## 5. Reflection Phase Extraction (VERY IMPORTANT)

AMC must be validated using reflection phase.

### In CST:

1. Use unit cell boundary conditions (periodic)
2. Apply Floquet port
3. Extract reflection phase vs frequency

---

### Target Condition

Reflection phase = 0° at f0

Bandwidth:
- Phase between +90° to -90°

---

## 6. AMC Array Formation

### Minimum Size

rows = 3 to 10  
cols = 3 to 10  

Minimum rule:
array dimension ≥ 3 × patch size

---

### Replication

- Periodic replication using p
- No overlap
- Uniform spacing

---

## 7. Integration with Patch Antenna

### Structure

Patch  
↓  
Air gap  
↓  
AMC  
↓  
Ground  

---

### Spacing Rule (CRITICAL)

h_gap = (0.02 to 0.08) * lambda0  

Too small:
- detuning
- strong coupling

Too large:
- weak AMC effect

---

### Alignment

- Patch center = AMC center
- Misalignment reduces gain

---

## 8. Frequency Tuning Loop (CST + ANN)

### Step 1: Initial Design

Generate:
p, a, g

---

### Step 2: Simulate Unit Cell

Get reflection phase curve

---

### Step 3: Evaluate

If phase( f_target ) > 0:
→ frequency too low → decrease a or increase g

If phase( f_target ) < 0:
→ frequency too high → increase a or decrease g

---

### Step 4: Iterate

Repeat until:
phase ≈ 0° at target frequency

---

## 9. Dataset Generation (Advanced)

### Inputs

- target_frequency
- patch dimensions
- substrate properties

---

### Outputs

- p
- a
- g
- h_gap
- array size

---

### Noise

param = ideal * (1 ± 5%)

---

### Labels

- reflection_phase_center
- bandwidth
- gain improvement
- back lobe reduction

---

## 10. Acceptance Criteria

accepted = (
 abs(f_amc - f_patch) < 3%
 AND reflection_phase ≈ 0°
 AND gain_improvement > 2 dB
)

---

## 11. Optimization Rules

Mismatch:
- tune a, g

Low gain:
- increase array size

Poor phase bandwidth:
- adjust substrate height

Detuning:
- adjust h_gap

---

## 12. Copilot Focus (STRICT RULES)

Copilot MUST:

1. Always compute lambda0 first
2. Scale all geometry from lambda
3. Enforce frequency matching
4. Maintain correct spacing (h_gap)
5. Ensure array size is sufficient
6. Use reflection phase for validation

Copilot MUST NOT:

- assign random dimensions
- ignore periodic structure
- skip reflection phase validation
- mismatch AMC and patch frequency

---

## 13. CST Implementation Steps

1. Create substrate
2. Create ground plane
3. Create unit cell patch
4. Apply periodic boundaries
5. Add Floquet port
6. Extract reflection phase
7. Tune geometry
8. Build full array
9. Place patch antenna above AMC
10. Set air gap
11. Run full simulation
12. Log results

---

## END
