# CST Material Definition Fix - Complete Solution

## Error Fixed
**CST MICROWAVE STUDIO - History Error**
```
(8H3000ffff) The specified material does not exist: Copper_annealed (.Create)
```

With VBA code:
```
With Brick
  .Reset
  .Name "amc_ground"
  .Component "amc"
  .Material "Copper_annealed"
  .Create
End With
```

## Root Cause Analysis

The material was being **used** before being **defined** in CST:

1. AMC command package arrived with geometry commands (create_patch, create_ground, etc.)
2. Material resolver determined materials should be: Copper (annealed), FR-4 (lossy)
3. `stamp_materials_on_package()` patched material references into geometry commands
4. ❌ But NO `define_material` commands were generated to pre-define materials in CST
5. When execution engine ran commands, CST encountered `.Material "Copper_annealed"` without definition
6. CST rejected the material as non-existent

## Solution Implemented

Enhanced `src/utils/material_resolver.py` - `stamp_materials_on_package()` function:

### Before Fix
```python
def stamp_materials_on_package(command_package, choice):
    # ... patch material references into commands ...
    patched["commands"] = commands  # ❌ No material definitions!
    return patched
```

### After Fix
```python
def stamp_materials_on_package(command_package, choice):
    # ... patch material references into commands ...
    
    # NEW: Generate define_material commands for each unique material
    material_defs = []
    for mat in sorted(unique_materials):
        define_cmd = {
            "seq": len(material_defs) + 1,
            "command": "define_material",
            "params": {
                "name": mat,
                "kind": "conductor" or "substrate",
                "conductivity_s_per_m": <known_value>,
            },
        }
        material_defs.append(define_cmd)
    
    # NEW: Prepend material definitions to command list
    patched["commands"] = material_defs + commands  # ✅ Materials defined first!
    return patched
```

## Execution Order - Before vs After

### Before (BROKEN ❌)
```
[0] create_component "amc"
[1] create_substrate "substrate" material="FR-4 (lossy)" ← CST: "What is FR-4 (lossy)?"
[2] create_patch "patch" material="Copper (annealed)" ← CST: "What is Copper_annealed?"
[3] create_ground_plane "ground" material="Copper (annealed)" ← ERROR!
```

### After (FIXED ✅)
```
[0] define_material "Copper (annealed)" ← Define in CST
[1] define_material "FR-4 (lossy)" ← Define in CST
[2] create_component "amc"
[3] create_substrate "substrate" material="FR-4 (lossy)" ← CST knows this material
[4] create_patch "patch" material="Copper (annealed)" ← CST knows this material
[5] create_ground_plane "ground" material="Copper (annealed)" ← CST knows this material
```

## Files Modified

### 1. `src/utils/material_resolver.py`
- Enhanced `stamp_materials_on_package()` function
- Added material info lookup table with standard properties
- Collects unique materials from commands
- Generates define_material commands for each material
- Prepends commands to ensure definition before use

### 2. `tests/unit/test_material_resolver.py`
- Updated 4 test cases to account for prepended define_material commands
- Tests verify:
  - Material definitions are generated
  - Definitions appear before geometry commands
  - Material properties are set correctly
  - Existing material assignments are preserved

## Test Results

### Unit Tests
✅ All 16 material resolver tests PASS
✅ All 1 AMC implementation test PASS  
✅ All 16 VBA generator tests PASS
**Total: 33/33 PASS**

### Integration Test
✅ Full pipeline verification:
- Materials resolved correctly
- Definitions generated for each material
- VBA code generated correctly
- Execution order verified

## Material Properties Included

The fix includes a lookup table with standard material properties:

| Material | Kind | Conductivity (S/m) |
|----------|------|-------------------|
| Copper (annealed) | conductor | 5.8e7 |
| Aluminum | conductor | 3.56e7 |
| Gold | conductor | 4.561e7 |
| Silver | conductor | 6.3e7 |
| FR-4 (lossy) | substrate | - (dielectric) |
| Rogers RT/duroid 5880 | substrate | - (dielectric) |
| Rogers RO3003 | substrate | - (dielectric) |

## VBA Output Example

For `define_material` "Copper (annealed)":

```vba
With Material
    .Reset
    .Name "Copper_annealed"
    .Folder ""
    .FrqType "all"
    .Type "Lossy metal"
    .Mu "1.0"
    .Kappa "5.8e+007"
    .Rho "8930.0"
    .ThermalType "Normal"
    .ThermalConductivity "401.0"
    .SpecificHeat "390", "J/K/kg"
    .MechanicsType "Isotropic"
    .YoungsModulus "120"
    .PoissonsRatio "0.33"
    .ThermalExpansionRate "17"
    .Colour "1", "1", "0"
    .Wireframe "False"
    .Transparency "0"
    .Create
End With
```

## Error Prevention

This fix prevents the error:
- ✅ Materials are ALWAYS pre-defined before use
- ✅ CST never encounters undefined material references
- ✅ Execution order is correct and deterministic
- ✅ Works with any material (known or unknown)

## Backward Compatibility

✅ All existing tests pass
✅ No breaking changes to APIs
✅ Gracefully handles materials without preset properties (uses CST defaults)
✅ Works with all antenna families (amc_patch, microstrip_patch, wban_patch)
