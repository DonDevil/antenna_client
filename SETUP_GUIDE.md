# Antenna Client - Setup & Connection Guide

## Overview
The Antenna Client has three main components that need to be configured:
1. **UI Application** (running now) ✅
2. **Backend Server** (antenna_server) - needs to be running
3. **CST Studio** (antenna simulator) - optional for simulation features

---

## 1. Window Size ✅
**Status**: Fixed - now 1200x700 pixels (reduced from 1400x900)

---

## 2. Backend Server Setup

### Option A: Run Local Development Server (Easy)

**Prerequisites:**
- Python 3.9+
- The antenna_server project (if you have it locally)

**Steps:**
```bash
# Navigate to antenna_server directory
cd path/to/antenna_server

# Install dependencies
pip install -r requirements.txt

# Start the server
python main.py
# This should print: "Uvicorn running on http://127.0.0.1:8000"
```

**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 [Press CTRL+C to quit]
```

**How to Verify:**
- Open browser and go to `http://localhost:8000/docs`
- You should see the Swagger API documentation

### Option B: Use Mock Server (Testing Only)

If you don't have the antenna_server, you can run the mock server included in the tests:

```bash
# From antenna_client directory
python -m pytest tests/test_server_communication.py -v --tb=short
```

### Option C: Remote Server Connection

If you want to connect to a remote server:

1. Edit `config.json`:
```json
{
  "server": {
    "base_url": "http://your-server-ip:8000",
    "timeout_sec": 60,
    "retry_count": 3,
    "retry_backoff": 2.0
  }
}
```

2. Restart the Antenna Client

---

## 3. CST Studio Connection

### System Requirements
- **CST Studio Suite 2024** (or compatible version)
- Installation path: `C:\Program Files\CST Studio Suite 2024\CST Studio.exe`

### Setup Steps

#### If you have CST installed:
1. Verify installation path matches in `config.json`:
```json
{
  "cst": {
    "executable_path": "C:\\Program Files\\CST Studio Suite 2024\\CST Studio.exe",
    "project_dir": "C:\\Users\\YourUsername\\Documents\\CST Projects",
    "default_units": "mm",
    "frequency_units": "ghz",
    "auto_save": true,
    "save_interval_sec": 300
  }
}
```

2. Create the project directory (if it doesn't exist):
```cmd
mkdir "C:\Users\YourUsername\Documents\CST Projects"
```

3. Restart the application

#### If you don't have CST:
- CST simulation features will be disabled
- You can still use the chat interface for antenna design discussions
- Purchase CST from: https://www.3ds.com/products/simulia/cst

---

## 4. How the Application Works

### Without Server (Demo Mode)
- ✅ Chat interface works
- ✅ Design panel displays
- ❌ Message submissions won't send (no backend)
- ❌ No antenna optimization

### With Server (Full Mode)
- ✅ Chat interface works
- ✅ Send design requests to server
- ✅ Receive antenna design recommendations
- ✅ Get optimization results

### With CST (Simulation Mode)
- ✅ All of the above
- ✅ Simulate antenna designs in CST Studio
- ✅ Extract S-parameters and radiation patterns
- ✅ Iterate on designs based on measurements

---

## 5. Server Configuration Details

### Current Config (config.json)
```json
{
  "server": {
    "base_url": "http://localhost:8000",
    "timeout_sec": 60,
    "retry_count": 3,
    "retry_backoff": 2.0
  }
}
```

### Available Endpoints (If Server is Running)
- `GET /health` - Server health check
- `POST /api/v1/optimize` - Antenna optimization request
- `GET /api/v1/results/{design_id}` - Get optimization results
- `POST /api/v1/simulate` - Trigger CST simulation

### Test Server Connection
```bash
# From PowerShell in antenna_client directory
curl http://localhost:8000/health
# Expected response: {"status": "healthy", "version": "1.0.0"}
```

---

## 6. Troubleshooting

### "Server not available" message
1. Check if antenna_server is running
   ```bash
   # Look for processes using port 8000
   netstat -ano | findstr :8000
   ```
2. If not running, start it with `python main.py` in antenna_server directory
3. Check `config.json` for correct `base_url`

### "CST Studio not found" message
1. Check if CST is installed: `C:\Program Files\CST Studio Suite 2024\CST Studio.exe`
2. Update `executable_path` in `config.json` if installed elsewhere
3. CST features will gracefully disable if not found

### Chat not sending messages
1. Verify server is running (`http://localhost:8000/health` should return status)
2. Check browser console for error messages
3. Review logs in `logs/` directory

### Keyboard shortcuts not working
- Enter: Send message
- Shift+Enter: New line
- Escape: Clear input

---

## 7. Next Steps

**Option 1 - Demo (Recommended for Testing)**
Just run the UI and explore. Server connection will auto-retry.

**Option 2 - With Server**
1. Start antenna_server
2. Restart antenna_client
3. Try sending a design request

**Option 3 - Full Stack** 
1. Start antenna_server
2. Install CST Studio
3. Configure paths in config.json
4. Run antenna_client
5. Try optimization with simulation

---

## 8. Key Files

| File | Purpose | Edit If |
|------|---------|---------|
| `config.json` | Server & CST settings | You have different server/CST paths |
| `ui/main_window.py` | Window size & layout | You want to change window dimensions |
| `comm/server_connector.py` | Server communication | You want to add new endpoints |
| `logs/antenna_client.log` | Application logs | Debugging issues |

---

**Last Updated**: April 3, 2026  
**Version**: 1.0.0
