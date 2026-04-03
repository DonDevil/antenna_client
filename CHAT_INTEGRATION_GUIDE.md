# Chat Integration & Server Communication Guide

## ✅ Fixed Issues

### 1. **Request Schema Alignment**
Updated `comm/request_builder.py` to match antenna_server's `optimize_request.v1` schema exactly.

**Key Fields:**
- `schema_version`: Must be `"optimize_request.v1"`
- `target_spec`: Requires `frequency_ghz` and `bandwidth_mhz` (in MHz, not percent)
- `design_constraints`: Requires `allowed_materials` and `allowed_substrates`
- `optimization_policy`: Requires specific structure with acceptance criteria
- `runtime_preferences`: Requires llm_temperature, timeout_budget_sec, priority
- `client_capabilities`: Requires all capability flags

### 2. **Material Names**
Updated to use exact names from antenna_server capabilities:
- **Conductors**: `"Copper (annealed)"` (NOT `"copper"`)
- **Substrates**: `"FR-4 (lossy)"` (NOT `"FR4"`)

### 3. **Chat Integration**
Created `utils/chat_message_handler.py` that:
- Listens to chat widget's `message_submitted` signal
- Sends messages to server via `/api/v1/optimize` endpoint
- Handles responses in background thread (non-blocking UI)
- Displays responses in chat widget

### 4. **Main Window Integration**
Updated `ui/main_window.py` to:
- Create `ChatMessageHandler` instance
- Connect handler to chat widget
- Automatically process incoming messages

---

## How the Chat Now Works

### User Flow:
1. User types message in chat input
2. Presses **Enter** or clicks **Send**
3. Message appears in chat as "You (HH:MM:SS)"
4. "⏳ Sending to server..." appears (system message)
5. Message sent to server `POST /api/v1/optimize`
6. Server processes optimization request
7. Response received and displayed as "Assistant (HH:MM:SS)"

### Background Processing:
- Message sending happens in `MessageSenderWorker` thread
- UI stays responsive (no freezes)
- Errors display as "❌ Error: [message]"

---

## Server Schema Reference

### Request Structure (Required Fields):
```json
{
  "schema_version": "optimize_request.v1",
  "user_request": "I need a 2.4 GHz patch antenna with 200 MHz bandwidth",
  "target_spec": {
    "frequency_ghz": 2.4,
    "bandwidth_mhz": 200,
    "antenna_family": "microstrip_patch"
  },
  "design_constraints": {
    "allowed_materials": ["Copper (annealed)"],
    "allowed_substrates": ["FR-4 (lossy)"]
  },
  "optimization_policy": {
    "mode": "auto_iterate",
    "max_iterations": 15,
    "stop_on_first_valid": false,
    "acceptance": {
      "center_tolerance_mhz": 50,
      "minimum_bandwidth_mhz": 100,
      "maximum_vswr": 2.0,
      "minimum_gain_dbi": 0,
      "minimum_return_loss_db": -20
    },
    "fallback_behavior": "best_effort"
  },
  "runtime_preferences": {
    "require_explanations": true,
    "persist_artifacts": true,
    "llm_temperature": 0.5,
    "timeout_budget_sec": 300,
    "priority": "normal"
  },
  "client_capabilities": {
    "supports_farfield_export": true,
    "supports_current_distribution_export": true,
    "supports_parameter_sweep": true,
    "max_simulation_timeout_sec": 600,
    "export_formats": ["json", "csv", "txt"]
  }
}
```

### Supported Values:

**Antenna Families:**
- `"amc_patch"`
- `"microstrip_patch"`
- `"wban_patch"`

**Conductor Materials:** (from capabilities)
- `"Copper (annealed)"`
- `"Aluminum"`
- `"Silver"`
- `"Gold"`

**Substrate Materials:** (from capabilities)
- `"FR-4 (lossy)"`
- `"Rogers RT/duroid 5880"`
- `"Rogers RO3003"`
- `"Rogers RO4350B"`

**Optimization Modes:**
- `"single_pass"` - One optimization iteration
- `"auto_iterate"` - Multiple iterations until convergence

**Fallback Behaviors:**
- `"best_effort"` - Return best result found
- `"return_error"` - Return error if no solution
- `"require_user_confirmation"` - Ask user before proceeding

**Priorities:**
- `"normal"` - Standard processing
- `"research"` - Research/extended analysis mode

---

## Files Updated

| File | Changes |
|------|---------|
| `comm/request_builder.py` | Complete rewrite to match antenna_server schema exactly |
| `utils/chat_message_handler.py` | **NEW** - Handles chat↔server communication |
| `ui/main_window.py` | Added ChatMessageHandler initialization |
| `ui/chat_widget.py` | Added support for "system" message type |

---

## Testing

**Test the request format:**
```bash
python diagnose_server.py
```

Should show:
- ✅ Request payload prints with correct structure
- Status 422 → Schema validation failed (check materials/substrates)
- Status other → Server processing started

**Test the full app:**
```bash
python main.py
```

Then:
1. Type message: "I need a 2.4 GHz antenna"
2. Click Send or press Enter
3. Watch for response from server

---

## Troubleshooting

### "Material 'X' is not allowed for family 'Y'"
- Check `design_constraints.allowed_materials`
- Must match exact names from antenna_server capabilities
- Only "Copper (annealed)" is typically allowed for patches

### "Substrate 'X' is not allowed"  
- Check `design_constraints.allowed_substrates`
- Use "FR-4 (lossy)" for most patches
- Use "Rogers" variants for low-loss requirements

### Messages not sending
1. Verify server is running: `python health_check.py`
2. Check logs in `logs/antenna_client.log`
3. Restart the application

### Chat stuck showing "Sending to server..."
- Wait 30 seconds (timeout)
- Check server logs
- Restart application

---

## Next Steps

**Fully Integrated Features:**
✅ Server connection check (Tools → Check Connection)  
✅ Chat message sending  
✅ Server response display  
✅ Async non-blocking operation  

**Still Needed:**
- Real-time server feedback during optimization
- CST simulation file generation
- Result export functionality
- Design iteration system

---

**Last Updated**: April 3, 2026  
**Schema Version**: optimize_request.v1  
**Server**: 192.168.234.89:8000
