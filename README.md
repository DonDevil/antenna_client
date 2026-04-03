# Antenna Optimization Client

A modular Windows desktop application for iterative antenna design optimization through conversational AI.

**Version**: 0.1.0 (Phase 1 - Foundation)

## Quick Start

### Prerequisites
- Python 3.10 or higher
- Windows 10/11
- CST Studio Suite (optional, required for full functionality)

### Development Setup

```bash
# Clone repository
git clone <repo-url>
cd antenna_client

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run application
python main.py
```

### Configuration

Copy `config.json` to your home directory or modify locally:
```json
{
  "server": {
    "base_url": "http://localhost:8000",
    "timeout_sec": 60
  }
}
```

## Project Structure

```
antenna_client/
├── ui/                  # User interface components
├── comm/                # Server communication layer
├── session/             # State management and persistence
├── cst/                 # CST Studio automation (Phase 3+)
├── executor/            # Command execution (Phase 3+)
├── utils/               # Logging, validation, constants
├── main.py              # Entry point
├── config.json          # Configuration template
└── requirements.txt     # Python dependencies
```

## Development Phases

- **Phase 1** (Current): Foundation, basic UI, server connectivity
- **Phase 2**: Chat interface, intent parsing
- **Phase 3**: CST integration, VBA generation
- **Phase 4**: Measurement extraction
- **Phase 5**: Feedback loop and iteration
- **Phase 6**: Error recovery and production readiness

## Key Features (Phase 1)

- ✓ Project structure and module organization
- ✓ Basic PyQt6 UI with menu bar
- ✓ Async HTTP client for server communication
- ✓ In-memory session management
- ✓ Structured logging
- ✓ Configuration management

## Testing

```bash
pytest tests/
```

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed architecture documentation
- Phase-specific implementation guides coming soon

## Support

For issues or questions, please open a GitHub issue or contact the team.

## License

[TBD]
