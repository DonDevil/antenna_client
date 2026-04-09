# Rectangular Microstrip Patch Antenna Design Rules

## 1. Overview
A rectangular microstrip patch antenna is a planar antenna consisting of:
- Metallic patch (radiating element)
- Dielectric substrate
- Ground plane

Operates in TM10 mode:
- Length (L) controls resonance
- Width (W) affects radiation efficiency and bandwidth

---

## 2. Inputs
Target:
- target_frequency_ghz
- target_bandwidth_mhz
- target_minimum_gain_dbi
- target_maximum_vswr
- target_minimum_return_loss_db

Material:
- substrate_epsilon_r
- substrate_height_mm
- substrate_loss_tangent

---

## 3. Core Equations

c = 3e8

W = c / (2 * f0 * sqrt((er + 1)/2))

eeff = (er + 1)/2 + (er - 1)/2 * (1 + 12*h/W)^(-0.5)

dL = 0.412*h * ((eeff + 0.3)*(W/h + 0.264)) / ((eeff - 0.258)*(W/h + 0.8))

Leff = c / (2 * f0 * sqrt(eeff))

L = Leff - 2*dL

---

## 4. Feed Design

Wf ≈ (0.03 to 0.08) * lambda0  
lambda0 = c / f0

feed_offset_y = (0.2 to 0.4) * L  
feed_offset_x = W / 2

---

## 5. Substrate

substrate_length = L + 6*h  
substrate_width  = W + 6*h  

---

## 6. Outputs

- patch_length_mm
- patch_width_mm
- substrate_length_mm
- substrate_width_mm
- feed_width_mm
- feed_length_mm
- feed_offset_x_mm
- feed_offset_y_mm

---

## 7. Relationships

- Increase er → smaller antenna
- Increase h → higher bandwidth, lower efficiency
- Increase W → higher efficiency
- Increase L → lower frequency

---

## 8. Performance Metrics

Return Loss < -10 dB  
VSWR < 2  
Gain: 5–9 dBi  
Bandwidth = f_high - f_low  

---

## 9. Acceptance

accepted = (
 abs(actual_frequency - target_frequency) < 5%
 AND vswr < 2
 AND return_loss < -10
)

---

## 10. Troubleshooting

Frequency too high → increase L  
Frequency too low → decrease L  

Bad matching → adjust feed_offset_y  

Low bandwidth → increase h  

Low gain → increase W  

---

## 11. Optimization Loop

1. Generate geometry  
2. Run CST  
3. Compare results  
4. Adjust parameters  
5. Save data  

---

## 12. Dataset Rules

frequency: 1–6 GHz  
er: 2.2–6  
h: 0.8–3 mm  

param = ideal * (1 ± 5%)

---

## END
