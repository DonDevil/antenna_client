# Installation & Usage Guide

**Current Version**: 0.1.0  
**Status**: Production Ready  
**Last Updated**: April 6, 2026

---

## Quick Start (5 minutes)

```bash
# 1. Clone and navigate
cd antenna_client

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run tests to verify setup
python run_integration_tests.py

# 4. Start application
python main.py
```

---

## Prerequisites

- **Python**: 3.10 or higher
- **OS**: Windows 10/11
- **RAM**: 2GB minimum
- **CST Studio Suite**: Optional (required for full functionality with real antenna design)
- **antenna_server**: Running at `http://localhost:8000` (can use mock for testing)

Check Python version:
```bash
python --version
# Output: Python 3.10.x or higher
```

---

## Installation

### 1. Clone Repository

```bash
git clone <repo-url>
cd antenna_client
```

### 2. Create Virtual Environment (Recommended)

```bash
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1

# Or use existing virtualenv
.\env310\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Key Packages**:
- `PySide6==6.7.2` - Qt-based UI
- `httpx==0.27.2` - Async HTTP client
- `pydantic==2.11.10` - Data validation
- `websockets==13.0` - Real-time streaming (optional)
- `aiohttp==3.9.5` - Async utilities
- `pytest==8.3.3` - Testing framework

### 4. Verify Installation

```bash
# Test imports
python -c "import PySide6, httpx, pydantic; print('OK')"

# Run integration tests
python run_integration_tests.py
```

Expected output:
```
Total Tests: 12
[OK] Passed: 12
[FAIL] Failed: 0
Success Rate: 100.0%
[OK] ALL TESTS PASSED - READY FOR PRODUCTION
```

---

## Configuration

### Config File

Create or edit `config.json`:

```json
{
  "server": {
    "base_url": "http://localhost:8000",
    "timeout_sec": 60
  },
  "client": {
    "app_name": "Antenna Optimization Client",
    "version": "0.1.0"
  },
  "logging": {
    "level": "INFO",
    "file": "logs/antenna_client.log"
  }
}
```

### Environment Variables

```bash
# Set logging level
set LOG_LEVEL=DEBUG

# Set server URL
set SERVER_URL=http://your-server:8000

# Set session directory
set SESSION_DIR=test_checkpoints
```

---

## Running the Application

### Start the UI Application

```bash
python main.py
```

The application will:
1. Load configuration from `config.json`
2. Perform startup health check
3. Load server capabilities
4. Display main window with chat interface
5. Poll for model warm-up (if LLM/ANN loading)

### Application Flow

```
Startup
  ↓
[1] Health Check → Server responding?
  ├─ Yes → Continue
  └─ No → Error, retry
  ↓
[2] Load Capabilities → What can server do?
  ├─ Success → Continue
  └─ Error → Retry
  ↓
[3] Warm-up Models → LLM/ANN ready?
  ├─ Ready → Show main window
  ├─ Loading → Show progress (poll)
  └─ Timeout → Continue anyway
  ↓
[4] Main Window → Ready for input
  ├─ Chat interface
  ├─ Design panel
  └─ Status bar
```

---

## Testing

### Run All Tests

```bash
python run_integration_tests.py
```

### Run Specific Tests

```bash
# Run only E2E tests
pytest tests/integration/test_integration_suite.py::TestEndToEndFlow -v

# Run only Session Recovery tests
pytest tests/integration/test_integration_suite.py::TestSessionRecovery -v

# Run with coverage
pytest tests/integration/ --cov=comm --cov=session --cov=executor
```

### Test Modes

**Mock Mode** (Default):
```bash
# Tests run with mock server (no real antenna_server needed)
python run_integration_tests.py
```

**Real Server Mode**:
```bash
# Make sure antenna_server is running
python antenna_server/main.py

# Then run tests (they'll detect real server and use it)
python run_integration_tests.py
```

### Expected Results

```
E2E TESTS:
[OK] E2E-1: Health Check
[OK] E2E-2: Load Capabilities
[OK] E2E-3: Optimize Request
[OK] E2E-4: Command Execution
[OK] E2E-5: Client Feedback

RECOVERY TESTS:
[OK] Recovery-1: Create Session
[OK] Recovery-2: Load Session
[OK] Recovery-3: Update Metadata

PAYLOAD TESTS:
[OK] Payload-1: Request Schema
[OK] Payload-2: Feedback Schema
[OK] Payload-3: Error Codes

OVERALL: 11 PASSED, 0 FAILED ✓
```

---

## Development

### Project Structure

```
antenna_client/
├── main.py                          # Application entry point
├── requirements.txt                 # Python dependencies
├── config.json                      # Configuration template
├── run_integration_tests.py          # Test runner
│
├── ui/                              # User interface
├── comm/                            # Server communication
├── session/                         # Session management
├── executor/                        # Command execution
├── utils/                           # Utilities
├── tests/                           # Integration tests
│
└── logs/                            # Log files
    └── antenna_client.log           # Application log
```

### Debug Mode

```bash
# Set log level to DEBUG
set LOG_LEVEL=DEBUG

# Run application
python main.py

# Check logs
cat logs/antenna_client.log
```

### Common Issues

**Issue**: `No module named 'websockets'`  
**Solution**:
```bash
pip install websockets aiohttp
```

**Issue**: `ConnectionRefusedError: antenna_server not running`  
**Solution**:
```bash
# Use mock server (default)
python run_integration_tests.py

# Or start antenna_server
python antenna_server/main.py
```

**Issue**: `UnicodeDecodeError` in tests  
**Solution**: Already fixed in latest version, update code

**Issue**: Session files not persisting  
**Solution**: Check `test_checkpoints/` directory permissions

---

## Usage Examples

### 1. Basic Optimization Design

**User Input**:
```
"Design a microstrip patch antenna at 2.45 GHz with 100 MHz bandwidth"
```

**Application Flow**:
1. Parse user intent
2. Build optimization request
3. Send to antenna_server
4. Receive command package
5. Execute VBA commands in CST
6. Submit feedback with results
7. Display results and recommendations

### 2. Iterative Refinement

**Iteration Loop**:
```
Iteration 0:
  ├─ Send initial design
  ├─ Get command package
  ├─ Run CST simulation
  ├─ Measure results
  └─ Submit feedback

Iteration 1:
  ├─ Server reviews feedback
  ├─ Generates new design
  ├─ Send command package  
  ├─ Run CST simulation
  ├─ Measure results
  └─ Submit feedback

... (up to max_iterations)
```

### 3. Session Recovery

**Restart Application**:
```bash
python main.py
```

Application will:
1. Load session from `test_checkpoints/sessions.json`
2. Restore iteration history
3. Recover design parameters
4. Allow continuing from last checkpoint

---

## Server Integration

### Connecting to antenna_server

**Remote Server**:
```json
{
  "server": {
    "base_url": "http://192.168.1.100:8000",
    "timeout_sec": 60
  }
}
```

**Local Development**:
```json
{
  "server": {
    "base_url": "http://localhost:8000",
    "timeout_sec": 60
  }
}
```

### Health Check

```bash
# Manual health check
curl http://localhost:8000/api/v1/health

# Expected response
{
  "status": "ok",
  "service": "AMC Antenna Optimization Server",
  "ann_status": "available",
  "llm_status": "available"
}
```

---

## Performance Optimization

### Connection Pooling

Connection pooling is automatically enabled in httpx:
```python
# Reuses connections
async with ServerConnector(url) as connector:
    response1 = await connector.get("/api/v1/health")
    response2 = await connector.get("/api/v1/capabilities")
    # Second request reuses connection
```

### Session Caching

Session data is persisted to avoid repeated re-creation:
```
First run:  Create → Persist
Second run: Load from disk
```

### Batch Operations

For multiple requests, use context manager:
```python
async with ServerConnector(url) as connector:
    # All requests reuse same connection
    for i in range(10):
        result = await connector.post("/endpoint", json=data)
```

---

## Deployment

### Production Checklist

- [ ] All 12 tests pass (`python run_integration_tests.py`)
- [ ] `config.json` points to production antenna_server
- [ ] Log files configured for production path
- [ ] CST Studio Suite installed and licensed (if needed)
- [ ] Firewall allows connection to antenna_server
- [ ] Enough disk space for test_checkpoints/ (sessions)
- [ ] Python 3.10+ installed with all requirements

### Production Config

```json
{
  "server": {
    "base_url": "http://production-server:8000",
    "timeout_sec": 120
  },
  "logging": {
    "level": "INFO",
    "file": "/var/log/antenna_client/antenna_client.log"
  }
}
```

### Deployment Steps

1. Clone on production machine
2. Create virtual environment
3. Install requirements: `pip install -r requirements.txt`
4. Update `config.json` with production server URL
5. Run tests: `python run_integration_tests.py`
6. Start application: `python main.py`

---

## Support & Troubleshooting

### Getting Help

1. **Check logs**: `cat logs/antenna_client.log`
2. **Run tests**: `python run_integration_tests.py`
3. **Verify connection**: `curl http://localhost:8000/api/v1/health`
4. **Check config**: `cat config.json`
5. **Inspect sessions**: `dir test_checkpoints/`

### Debug Information

```bash
# Show Python environment
python -c "import sys; print(sys.executable)"

# List installed packages
pip list

# Test specific import
python -c "from comm.api_client import ApiClient; print('OK')"
```

### Reporting Issues

Include when reporting issues:
1. **Output**: Full error message
2. **Logs**: Content of `logs/antenna_client.log`
3. **Test results**: Output of `python run_integration_tests.py`
4. **Config**: Content of `config.json` (remove sensitive data)
5. **Environment**: Python version, OS, network setup

---

## Updating

### Check Current Version

```bash
grep "version" config.json
```

### Update Dependencies

```bash
pip install --upgrade -r requirements.txt
```

### Migrate Sessions

Sessions are automatically migrated. Just close and restart:
```bash
python main.py
```

---

**Status**: ✅ Ready for Production  
**Tests**: 12/12 PASS  
**Last Updated**: April 6, 2026
