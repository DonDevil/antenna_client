# Connection Check Feature

## Overview
The Antenna Client now has a built-in **"Check Connection"** button that verifies server and CST Studio availability without restarting the app.

## How to Use

### Option 1: Using the Menu
1. Click **Tools** menu → **Check Connection**
2. The app will check both server and CST connectivity
3. A dialog will appear showing the results
4. Status bar at the bottom will update to reflect the connection state

### Option 2: Using Command Line
```powershell
python health_check.py
```

## What Gets Checked

| Component | Check | Endpoint |
|-----------|-------|----------|
| **Server** | HTTP connection to API | `{base_url}/api/v1/health` |
| **CST Studio** | File existence check | `config.json` → `executable_path` |

## Dialog Results

### ✅ All Connected (Green ✅)
- Server: Connected
- CST: Available

### ⚠️ Partial Connection (Orange ⚠️)
- One of server/CST is connected
- One is unavailable
- Chat will work, but simulation may be limited

### ❌ Disconnected (Red ❌)
- Server: Not responding or unreachable
- CST: Not installed
- UI will work in demo mode only

## Status Bar Indicators
Bottom of window shows real-time status:
- `Server: Connected` or `Server: Disconnected`
- `CST: Available` or `CST: Not Available`

## Troubleshooting

### "Connection Check" takes a while
- Normal for first check (5-second timeout)
- Usually faster after first check
- Happens in background, UI stays responsive

### Still says "Disconnected" after clicking?
1. Verify server is running at `http://192.168.234.89:8000`
2. Open browser to confirm: `http://192.168.234.89:8000/api/v1/health`
3. Check `config.json` for correct server URL
4. Click "Check Connection" again to retry

### Want to change server address?
1. Edit `config.json`
2. Update `server.base_url` value
3. Click "Tools" → "Check Connection" to verify

## Technical Details

### Files Modified
- `ui/main_window.py` - Added Tools menu and connection check UI
- `utils/connection_checker.py` - New module for checking connectivity
- `health_check.py` - Updated to use correct /api/v1/health endpoint

### How It Works
1. Click "Check Connection" → Spawns background thread
2. Thread calls `ConnectionChecker.check_all()`
3. Async server check + sync CST check run in parallel
4. Results emitted back to UI via Qt signals
5. Dialog displays results, status bar updates
6. Your app stays responsive during check

### Performance
- Server check: ~5 seconds (with retries) or ~1 second if connected
- CST check: <100ms (instant file check)
- UI remains responsive - no freezing

## Keyboard Shortcuts
- **Ctrl+Alt+C** - Could be added for quick check (currently not assigned)

---

**Updated**: April 3, 2026
