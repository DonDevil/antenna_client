# CST Command Console Reference

This document covers all commands currently supported by `test_cst_command_console.py`.

## General Input Format

Each line in the console uses this format:

```text
<command_name> <optional_json_params>
```

- `command_name`: one of the supported commands below.
- `optional_json_params`: JSON object with command parameters.

Examples:

```text
set_units
set_frequency_range {"start_ghz": 1.8, "stop_ghz": 3.2}
```

## Common Behaviors

- If no JSON is provided, the console uses built-in defaults.
- If partial JSON is provided, your values override defaults.
- `create_project` should be run before geometry/solver/export commands.
- `raw` lets you execute direct VBA text.

---

## Meta Commands

### help
Show help and examples.

Usage:
```text
help
```

Options:
- none

### list
Alias for help.

Usage:
```text
list
```

Options:
- none

### quit
Exit the console.

Usage:
```text
quit
```

Options:
- none

### exit
Alias for quit.

Usage:
```text
exit
```

Options:
- none

---

## Core Project Commands

### create_project
Create/activate a new CST MWS project.

Usage:
```text
create_project {"project_name": "demo_patch"}
```

Options:
- `project_name` (string): project label used by the test console.

Default:
- `project_name`: `command_console_project`

---

### set_units
Set model units in CST.

Usage:
```text
set_units
set_units {"geometry": "mm", "frequency": "ghz"}
```

Options:
- `geometry` (string): geometry unit. Current expected value: `mm`.
- `frequency` (string): frequency unit. Current expected value: `ghz`.

Default:
```json
{"geometry": "mm", "frequency": "ghz"}
```

---

### set_frequency_range
Set solver frequency sweep range.

Usage:
```text
set_frequency_range
set_frequency_range {"start_ghz": 1.9, "stop_ghz": 2.9}
```

Options:
- `start_ghz` (number): start frequency in GHz.
- `stop_ghz` (number): stop frequency in GHz.

Default:
```json
{"start_ghz": 1.9, "stop_ghz": 2.9}
```

---

## Material Commands

### define_material
Define a conductor or substrate material.

Usage:
```text
define_material
define_material {"name": "Copper (annealed)", "kind": "conductor", "conductivity_s_per_m": 58000000.0}
define_material {"name": "Rogers RT/duroid 5880", "kind": "substrate", "epsilon_r": 4.4, "loss_tangent": 0.02}
```

Options:
- `name` (string): material name.
- `kind` (string): `conductor` or `substrate`.
- `conductivity_s_per_m` (number): used for conductor.
- `epsilon_r` (number): relative permittivity for substrate.
- `loss_tangent` (number): loss tangent for substrate.

Default:
```json
{"name": "Copper (annealed)", "kind": "conductor", "conductivity_s_per_m": 58000000.0}
```

---

## Geometry Commands

### create_substrate
Create substrate brick.

Usage:
```text
create_substrate
create_substrate {"name": "substrate", "material": "FR-4 (lossy)", "length_mm": 56.0, "width_mm": 60.0, "height_mm": 1.6, "origin_mm": {"x": 0.0, "y": 0.0, "z": 0.0}}
```

Options:
- `name` (string)
- `material` (string)
- `length_mm` (number)
- `width_mm` (number)
- `height_mm` (number)
- `origin_mm` (object)
  - `x` (number)
  - `y` (number)
  - `z` (number)

Default:
```json
{"name": "substrate", "material": "FR-4 (lossy)", "length_mm": 56.0, "width_mm": 60.0, "height_mm": 1.6, "origin_mm": {"x": 0.0, "y": 0.0, "z": 0.0}}
```

---

### create_ground_plane
Create ground plane brick.

Usage:
```text
create_ground_plane
create_ground_plane {"name": "ground", "material": "Copper (annealed)", "length_mm": 56.0, "width_mm": 60.0, "thickness_mm": 0.035, "z_mm": 0.0}
```

Options:
- `name` (string)
- `material` (string)
- `length_mm` (number)
- `width_mm` (number)
- `thickness_mm` (number)
- `z_mm` (number)

Default:
```json
{"name": "ground", "material": "Copper (annealed)", "length_mm": 56.0, "width_mm": 60.0, "thickness_mm": 0.035, "z_mm": 0.0}
```

---

### create_patch
Create patch brick.

Usage:
```text
create_patch
create_patch {"name": "patch", "material": "Copper (annealed)", "length_mm": 31.0, "width_mm": 36.0, "thickness_mm": 0.035, "center_mm": {"x": 0.0, "y": 0.0, "z": 1.6}}
```

Options:
- `name` (string)
- `material` (string)
- `length_mm` (number)
- `width_mm` (number)
- `thickness_mm` (number)
- `center_mm` (object)
  - `x` (number)
  - `y` (number)
  - `z` (number)

Default:
```json
{"name": "patch", "material": "Copper (annealed)", "length_mm": 31.0, "width_mm": 36.0, "thickness_mm": 0.035, "center_mm": {"x": 0.0, "y": 0.0, "z": 1.6}}
```

---

### create_feedline
Create feedline brick.

Usage:
```text
create_feedline
create_feedline {"name": "feed", "material": "Copper (annealed)", "length_mm": 14.0, "width_mm": 0.8, "thickness_mm": 0.035, "start_mm": {"x": 0.0, "y": -8.0, "z": 1.6}, "end_mm": {"x": 0.0, "y": -22.0, "z": 1.6}}
```

Options:
- `name` (string)
- `material` (string)
- `length_mm` (number)
- `width_mm` (number)
- `thickness_mm` (number)
- `start_mm` (object): `x`, `y`, `z`
- `end_mm` (object): `x`, `y`, `z`

Default:
```json
{"name": "feed", "material": "Copper (annealed)", "length_mm": 14.0, "width_mm": 0.8, "thickness_mm": 0.035, "start_mm": {"x": 0.0, "y": -8.0, "z": 1.6}, "end_mm": {"x": 0.0, "y": -22.0, "z": 1.6}}
```

---

### create_port
Create excitation port.

Usage:
```text
create_port
create_port {"port_id": 1, "port_type": "discrete", "impedance_ohm": 50.0, "p1_mm": {"x": 0.0, "y": -22.0, "z": 1.6}, "p2_mm": {"x": 0.0, "y": -22.0, "z": 0.0}}
```

Options:
- `port_id` (integer)
- `port_type` (string): typically `discrete`
- `impedance_ohm` (number)
- `p1_mm` (object): port start point `x`, `y`, `z`
- `p2_mm` (object): port end point `x`, `y`, `z`
- `reference_mm` (object): fallback shorthand if `p1_mm` is omitted

Default:
```json
{"port_id": 1, "port_type": "discrete", "impedance_ohm": 50.0, "p1_mm": {"x": 0.0, "y": -22.0, "z": 1.6}, "p2_mm": {"x": 0.0, "y": -22.0, "z": 0.0}}
```

---

## Solver/Boundary Commands

### set_boundary
Set simulation boundary setup.

Usage:
```text
set_boundary
set_boundary {"boundary_type": "open_add_space", "padding_mm": 15.0}
```

Options:
- `boundary_type` (string): e.g. `open_add_space`
- `padding_mm` (number)

Default:
```json
{"boundary_type": "open_add_space", "padding_mm": 15.0}
```

---

### set_solver
Set solver mode and mesh target.

Usage:
```text
set_solver
set_solver {"solver_type": "time_domain", "mesh_cells_per_wavelength": 20}
```

Options:
- `solver_type` (string): e.g. `time_domain`
- `mesh_cells_per_wavelength` (integer/number)

Default:
```json
{"solver_type": "time_domain", "mesh_cells_per_wavelength": 20}
```

---

### run_simulation
Start simulation.

Usage:
```text
run_simulation
run_simulation {"timeout_sec": 600}
```

Options:
- `timeout_sec` (integer): timeout hint for run.

Default:
```json
{"timeout_sec": 600}
```

---

### add_farfield_monitor
Add a frequency-domain far-field monitor.

Usage:
```text
add_farfield_monitor
add_farfield_monitor {"frequency_ghz": 2.4, "name": "farfield_2p4ghz"}
```

Options:
- `frequency_ghz` (number): monitor frequency in GHz.
- `name` (string): monitor label.

Default:
```json
{"frequency_ghz": 2.4, "name": "farfield_2p4ghz"}
```

---

## Export/Metrics Commands

### export_s_parameters
Request S-parameter export.

Usage:
```text
export_s_parameters
export_s_parameters {"format": "json", "destination_hint": "s11"}
```

Options:
- `format` (string): `json`, `csv`, etc.
- `destination_hint` (string): e.g. `s11`.

Default:
```json
{"format": "json", "destination_hint": "s11"}
```

---

### extract_summary_metrics
Request summary metric extraction.

Usage:
```text
extract_summary_metrics
extract_summary_metrics {"metrics": ["center_frequency_ghz", "bandwidth_mhz", "return_loss_db", "vswr", "gain_dbi"]}
```

Options:
- `metrics` (array of strings)

Default:
```json
{"metrics": ["center_frequency_ghz", "bandwidth_mhz", "return_loss_db", "vswr", "gain_dbi"]}
```

---

### export_farfield
Export far-field data from CST result tree.

Usage:
```text
export_farfield
export_farfield {"format": "json", "frequency_ghz": 2.4, "destination_hint": "farfield"}
```

Options:
- `format` (string)
- `frequency_ghz` (number)
- `destination_hint` (string)

Behavior:
- Scans CST tree items for far-field results.
- Prefers the item closest to `frequency_ghz` when multiple far-field entries are available.
- Uses CST `FarfieldPlot` export routines after selecting the result item.
- Writes far-field source data to `artifacts/exports/<destination_hint>.txt`.
- Writes a summary report to `artifacts/exports/<destination_hint>_summary.txt`.
- Writes a theta cut to `artifacts/exports/<destination_hint>_theta_cut.txt`.
- Writes metadata to `artifacts/exports/<destination_hint>_meta.json`.

Default:
```json
{"format": "json", "frequency_ghz": 2.4, "destination_hint": "farfield"}
```

---

## Raw VBA Command

### raw
Execute direct VBA snippet without command mapping.

Usage:
```text
raw {"title": "quick_note", "code": "' test line"}
```

Options:
- `title` (string): history title for CST.
- `code` (string): VBA code text.

Default:
```json
{"title": "raw_vba_test", "code": "' raw vba test"}
```

---

## Typical Validation Sequence

Recommended command order when testing major CST flow:

```text
create_project {"project_name":"cmd_test_01"}
set_units
set_frequency_range

define_material {"name":"Copper (annealed)","kind":"conductor","conductivity_s_per_m":58000000}
define_material {"name":"FR-4 (lossy)","kind":"substrate","epsilon_r":4.4,"loss_tangent":0.02}

create_substrate
create_ground_plane
create_patch
create_feedline
create_port

set_boundary
set_solver
add_farfield_monitor
run_simulation

export_s_parameters
extract_summary_metrics
export_farfield
```

---

## Notes

- The console validates command mapping and VBA generation through the same client generator logic used by the app.
- If a command fails, keep the exact command line and error text so we can patch either:
  1. client VBA generator mapping, or
  2. CST COM invocation method compatibility.
