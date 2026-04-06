# Antenna Optimization Client

Windows client for conversational antenna design, server-driven optimization, and CST execution workflows.

## Quick Start

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

For automated validation:

```bash
python scripts/run_integration_tests.py
pytest tests -q
```

## Repository Layout

```text
antenna_client/
├── src/            # Application packages
├── tests/          # Unit and integration tests
├── scripts/        # Utility and validation scripts
├── docs/           # Active documentation and archived reports
├── config.json     # Runtime configuration
├── main.py         # Root launcher that forwards to src/main.py
└── requirements.txt
```

## Documentation

- See [docs/README.md](docs/README.md) for the documentation index.
- See [docs/SETUP.md](docs/SETUP.md) for installation and environment setup.
- See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for component layout.
- See [docs/API.md](docs/API.md) for the client-server contract.
- See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for test and maintenance guidance.

## Current Status

- The client is organized around a `src/` layout while preserving `python main.py` from the repository root.
- Integration support is wired for the configured server in [config.json](config.json).
- Historical one-off reports have been moved under `docs/archive/` to keep the root clean.
