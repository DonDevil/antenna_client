# Automatic Health Monitoring Guide

## Overview

The antenna client now features **automatic periodic health checking** that monitors server and CST availability without user intervention.

## Features

### 🚀 Automatic Startup Check
- Health check runs automatically when the app starts
- No menu click required
- Status indicators update immediately

### ⏱️ Periodic Monitoring
- Health checks run every **30 seconds** in the background
- Non-blocking: UI remains responsive during checks
- Status bar updates continuously

### 🔐 Connection Loss Detection
- App detects when server/CST connection is lost
- App detects when connection is restored  
- Status indicators reflect real-time connectivity
- Logs indicate when changes occur

## Status Indicators

The status bar at the bottom shows:

```
🟢 Server: Connected          🟢 CST: Available
```

- **🟢 Green**: Service is available and healthy
- **🔴 Red**: Service is unavailable or disconnected
- **⚪ Gray**: Checking status

## How It Works

### Automatic Flow
1. App starts → MainWindow initializes
2. HealthMonitor created with 30-second interval
3. First check runs immediately
4. Subsequent checks every 30 seconds
5. Status bar updates with results
6. If connection lost, indicators change to red
7. If connection restored, indicators change to green

### Background Thread
- Health checks run in background worker thread
- Qt signals/slots ensure thread-safe UI updates
- No blocking of user interactions

### Graceful Shutdown
- Health monitor stopped when app closes
- Background thread cleanly terminated
- No lingering processes

## Manual Connection Check

You can still manually check connections:
- **Tools menu** → **Check Connection**
- Shows detailed connection status dialog
- Useful for troubleshooting specific issues

## Configuration

To adjust check interval (edit `ui/main_window.py`):

```python
# Default: 30 seconds
self.health_monitor = HealthMonitor(self.status_bar, check_interval_sec=30)

# Change to 60 seconds:
self.health_monitor = HealthMonitor(self.status_bar, check_interval_sec=60)
```

## Logging

Health monitoring events appear in application logs:

```
INFO: Health monitor started (interval: 30s)
DEBUG: Health check completed: ['server', 'cst']
WARNING: 🔴 Server connection LOST
INFO: 🟢 Server connection RESTORED
```

## What Gets Checked

Each health check verifies:

1. **Server Status**
   - POST to `/api/v1/health`
   - Confirms antenna optimization model is ready
   - Checks connectivity and responsiveness

2. **CST Studio Status**
   - File existence check at configured path
   - Confirms CST executable is available
   - Detects if CST installation becomes unavailable

## Benefits

✅ **Always know connection status** - See at a glance if system is ready
✅ **Early problem detection** - Know immediately if connection drops
✅ **Non-intrusive** - Runs in background, doesn't block UI  
✅ **Automatic recovery detection** - Knows when systems come back online
✅ **Better reliability** - App aware of connectivity state for operations

## Troubleshooting

### Status indicator always red?
1. Check server is running at configured address
2. Check CST is installed at configured path
3. Use **Tools → Check Connection** for detailed error message

### Checks not running?
1. Check application logs for errors
2. Verify network connectivity
3. Confirm server is accessible

### Want to disable periodic checks?
- Comment out `health_monitor.start()` in `main_window.py`
- Manual check still available via Tools menu

## Technical Details

- **Check Interval**: 30 seconds (configurable)
- **Timeout**: 10 seconds per check
- **Thread Type**: QThread-based background worker
- **Update Method**: Qt signals/slots (thread-safe)
- **Retry Logic**: Built into connection checker
