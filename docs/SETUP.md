# Setup

## Requirements

- Windows 10 or 11
- Python 3.10+
- CST Studio Suite 2024 for CST execution features
- Network access to the optimization server configured in [config.json](../config.json)

## Environment

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Edit [config.json](../config.json) for your environment.

Important settings:

- `server.base_url`: optimization server base URL
- `server.timeout_sec`: request timeout
- `cst.executable_path`: CST executable location
- `cst.project_dir`: local CST project workspace

## Running

Application launcher:

```bash
python main.py
```

Health check:

```bash
python scripts/health_check.py
```

Integration validation:

```bash
python scripts/run_integration_tests.py
python scripts/run_real_integration_tests.py
```