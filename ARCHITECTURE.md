# Antenna Optimization Client - Architecture Plan

**Version**: 1.0  
**Target Platform**: Windows 10/11  
**Language**: Python 3.10+  
**Server Dependency**: antenna_server (Linux Ubuntu 24.04)

---

## Executive Summary

The antenna client is a modular Windows desktop application that:
1. **Provides conversational UI** for natural language antenna design requests
2. **Communicates with the server** via HTTP REST API (async)
3. **Receives high-level command packages** from server
4. **Translates commands to VBA** for CST execution
5. **Manages CST automation** via COM interface
6. **Extracts measurements** from simulations
7. **Sends feedback** to server for iterative refinement
8. **Persists design history** locally

**Design Philosophy**: Modular separation of concerns (UI, communication, execution, CST interface)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Client Application                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐  ┌──────────────────────────────┐    │
│  │   UI Layer       │  │   Command Executor Layer     │    │
│  ├──────────────────┤  ├──────────────────────────────┤    │
│  │ • Chat Window    │  │ • VBA Generator              │    │
│  │ • Design History │  │ • Command Validator          │    │
│  │ • Session Panel  │  │ • Execution Orchestrator     │    │
│  │ • Status Display │  │ • Progress Tracker           │    │
│  └────────┬─────────┘  └────────────┬─────────────────┘    │
│           │                         │                       │
│  ┌────────▼─────────────────────────▼────────┐            │
│  │   Session & State Management Layer         │            │
│  ├────────────────────────────────────────────┤            │
│  │ • Session Store (in-memory + SQLite)      │            │
│  │ • Design History                           │            │
│  │ • Configuration Manager                    │            │
│  │ • Error Recovery                           │            │
│  └────────┬─────────────────────────────────┘            │
│           │                                                │
│  ┌────────▼─────────────────────────────────┐            │
│  │   Communication Layer (HTTP Client)       │            │
│  ├────────────────────────────────────────────┤            │
│  │ • Server Connector (async httpx)          │            │
│  │ • Intent Parser (local fallback)          │            │
│  │ • Request/Response Handler                │            │
│  │ • Retry & Timeout Logic                   │            │
│  └────────┬─────────────────────────────────┘            │
│           │                                                │
│  ┌────────▼─────────────────────────────────┐            │
│  │   CST Interface Layer                     │            │
│  ├────────────────────────────────────────────┤            │
│  │ • COM Automation (pywin32)                │            │
│  │ • VBA Macro Injector                      │            │
│  │ • Result Extractor (S11 parser)           │            │
│  │ • Error Handler & Validation              │            │
│  │ • CST Project Manager                     │            │
│  └────────────────────────────────────────────┘            │
│                                                               │
│  ┌──────────────────────────────────────────┐              │
│  │   Utilities & Common Logging             │              │
│  └──────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
         ↓                                                ↓
    ┌────────────────────────────────────────────────┐  ┌──────────┐
    │  antenna_server (Linux)                        │  │ CST      │
    │  HTTP API on port 8000                         │  │ Studio   │
    └────────────────────────────────────────────────┘  └──────────┘
```

---

## Core Components (Modular Breakdown)

### **Layer 1: UI Component** (`ui/`)
**Responsibility**: User interaction, display, input handling

- **`chat_widget.py`**
  - Chatbot conversation window
  - Message display (user/assistant)
  - Input text field
  - Message history scrolling
  - Markdown rendering support

- **`design_panel.py`**
  - Current design specs display
  - Antenna family selector
  - Frequency/bandwidth input fields
  - Constraints editor
  - Quick-action buttons

- **`session_panel.py`**
  - Active session list
  - Design history browser
  - Load/save design actions
  - Session metadata display

- **`status_bar.py`**
  - Server connection status
  - CST availability indicator
  - Execution progress bar
  - Error/warning notifications

- **`main_window.py`**
  - Application entry point
  - Layout orchestration
  - Menu bar (File, Edit, Help)
  - Keyboard shortcuts

**Framework**: PyQt6 or PySimpleGUI (lightweight, Windows-native)

---

### **Layer 2: Command Execution** (`executor/`)
**Responsibility**: Translate high-level commands → VBA → CST execution

- **`command_parser.py`**
  - Parse `cst_command_package.v1` JSON
  - Validate command structure
  - Extract parameters
  - Handle version compatibility

- **`vba_generator.py`**
  - Convert each high-level command to VBA macro
  - Template-based generation (`templates/cmd_*.vba`)
  - Parameter substitution (geometry units, materials, etc.)
  - Error handling macros

- **`execution_engine.py`**
  - Orchestrate sequential command execution
  - Track execution state (pending → running → complete)
  - Handle on_failure policies (abort, skip, retry)
  - Accumulate errors + warnings
  - Emit progress events to UI

- **`progress_tracker.py`**
  - Track overall progress (% complete)
  - Per-command status
  - Estimated time remaining
  - Pause/resume capability (if supported)

**Dependencies**: VBA macro templates, command validation schemas

---

### **Layer 3: Session & State Management** (`session/`)
**Responsibility**: Persist and manage application state

- **`session_store.py`**
  - In-memory session cache
  - SQLite backend for persistence
  - Session CRUD operations
  - Query by session_id / trace_id

- **`design_history.py`**
  - Track completed designs
  - Store iterations per design
  - Retrieve previous designs for comparison
  - Export design to JSON/CSV

- **`config_manager.py`**
  - Client configuration (server URL, timeouts, etc.)
  - User preferences (UI theme, auto-connect, etc.)
  - Load/save to `config.json`

- **`error_recovery.py`**
  - Detect && recovery from network errors
  - CST crashes
  - Partial execution completion
  - Resume from checkpoint

**Storage**: `~\AppData\Local\AntennaClient\` (Windows standard)

---

### **Layer 4: Communication** (`comm/`)
**Responsibility**: HTTP communication with antenna_server

- **`server_connector.py`**
  - Async HTTP client (httpx)
  - Connection pooling
  - SSL/TLS support (future: proxy support)
  - Timeout & retry logic

- **`api_client.py`**
  - Wrapper around REST endpoints
  - `POST /api/v1/optimize` → send OptimizeRequest
  - `POST /api/v1/client-feedback` → send CST results
  - `POST /api/v1/chat` → send chat message
  - `GET /api/v1/health` → check server availability

- **`request_builder.py`**
  - Build OptimizeRequest from user intent
  - Construct design constraints
  - Set optimization policy
  - Attach client capabilities

- **`response_handler.py`**
  - Parse OptimizeResponse
  - Extract command package
  - Handle clarification requests
  - Process error responses

**Dependencies**: httpx, pydantic (for schema validation)

---

### **Layer 5: CST Interface** (`cst/`)
**Responsibility**: Direct CST Studio automation via COM

- **`cst_app.py`**
  - COM object connection to CST
  - Application lifecycle (launch, close, check status)
  - MWS (Model WorkSpace) access
  - Error handling for COM failures

- **`vba_executor.py`**
  - Inject VBA macro into CST
  - Execute macro via `add_to_history()`
  - Parse return values
  - Handle VBA runtime errors

- **`result_extractor.py`**
  - Parse S11 simulation results
  - Extract center frequency (GHz)
  - Calculate bandwidth (MHz)
  - Extract VSWR, return loss, gain
  - Parse farfield data (if available)

- **`project_manager.py`**
  - Create new CST project / open existing
  - Save project to disk
  - Export simulation results (S-params, field data)
  - Cleanup & temp file management

**Dependencies**: pywin32 (Windows COM), CST Studio Suite (installed on machine)

---

### **Layer 6: Utilities** (`utils/`)
**Responsibility**: Cross-cutting functionality

- **`logger.py`**
  - Structured logging
  - Multiple handlers (console, file, rotating)
  - Log levels (DEBUG, INFO, WARNING, ERROR)
  - Session-tagged output

- **`validators.py`**
  - Validate JSON schemas
  - Check parameter ranges
  - Verify CST project structure

- **`constants.py`**
  - Server URL, API version
  - Timeout defaults
  - CST paths, VBA templates location
  - UI color schemes, fonts

- **`decorators.py`**
  - `@async_task` - Run blocking tasks in thread pool
  - `@retry` - Retry with exponential backoff
  - `@timeout` - Enforce operation timeout

---

## Data Flow & Interactions

### **Scenario 1: User Submits Design Request**
```
1. User types in chat: "Design 2.4 GHz patch with 50 MHz BW"
   ↓ (UI captures input)
2. chat_widget sends text to session_store
   ↓ (Extract intent locally)
3. intent_parser extracts frequency/bandwidth
   ↓ (Build request)
4. request_builder creates OptimizeRequest
   ↓ (Send to server)
5. server_connector POST /api/v1/optimize
   ↓ (Wait for response)
6. response_handler receives OptimizeResponse
   ↓ (Extract command_package)
7. command_parser validates commands
   ↓ (Generate VBA)
8. vba_generator creates macros from commands
   ↓ (Execute)
9. execution_engine orchestrates CST execution
   ↓ (Extract results)
10. result_extractor parses S11 + metrics
    ↓ (Send feedback)
11. server_connector POST /api/v1/client-feedback
    ↓ (Store)
12. session_store logs iteration results
    ↓ (Update UI)
13. status_bar shows "Design complete: Fr=2.38 GHz, BW=52 MHz"
```

### **Scenario 2: Server Requests Refinement**
```
1. Server responds to feedback with next_iteration
   ↓
2. response_handler detects "status=auto_iterate"
   ↓
3. UI updates to show: "Server planning refinement..."
   ↓
4. New OptimizeResponse contains refined command_package
   ↓
5. execution_engine re-runs CST with new dimensions
   ↓
6. Loop back to step 10 of Scenario 1
```

---

## Development Phases

### **Phase 1: Foundation (Weeks 1-2)**
**Goal**: Establish project structure, basic UI, server connectivity

**Tasks**:
- [ ] Set up project structure (`ui/`, `comm/`, `session/`, `cst/`, `utils/`)
- [ ] Create basic PyQt6 main window with menu bar
- [ ] Implement session_store (in-memory only)
- [ ] Implement server_connector (httpx async client)
- [ ] Implement api_client (wrappers for GET /health, POST /optimize)
- [ ] Add logger & config_manager
- [ ] Create unit tests for api_client & session_store
- [ ] Add README with setup instructions

**Deliverables**:
- Working project scaffold
- Can connect to antenna_server
- Can send OptimizeRequest
- Can receive OptimizeResponse
- Basic logging to console

**Output Files**:
```
antenna_client/
├── ui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── chat_widget.py
│   ├── status_bar.py
│   └── styles.qss (PyQt6 stylesheet)
├── comm/
│   ├── __init__.py
│   ├── server_connector.py
│   └── api_client.py
├── session/
│   ├── __init__.py
│   └── session_store.py
├── utils/
│   ├── __init__.py
│   ├── logger.py
│   ├── constants.py
│   └── validators.py
├── main.py
├── config.json (template)
├── requirements.txt
└── README.md
```

---

### **Phase 2: Chat & Intent (Weeks 3-4)**
**Goal**: Full conversational interface with local fallback NLP

**Tasks**:
- [ ] Implement chat_widget with message history display
- [ ] Implement request_builder (convert intent → OptimizeRequest)
- [ ] Add local intent_parser (regex-based fallback for offline mode)
- [ ] Implement response_handler (parse OptimizeResponse)
- [ ] Add design_panel for specs display & editing
- [ ] Implement multi-turn chat (keep context across messages)
- [ ] Handle clarification_required responses
- [ ] Add message persistence to SQLite

**Deliverables**:
- Full chat interface with message history
- Can parse user intent locally
- Can handle server clarifications
- Persistent chat logs

**Output Files**:
```
ui/
├── chat_widget.py (expanded)
├── design_panel.py (new)
└── dialogs.py (clarification, parameter edit)

comm/
├── request_builder.py (new)
├── response_handler.py (new)
└── intent_parser.py (new, local fallback)

session/
├── chat_history.py (new)
└── design_store.py (new)
```

---

### **Phase 3: CST Integration (Weeks 5-6)**
**Goal**: COM interface, VBA generation, basic execution

**Tasks**:
- [ ] Implement cst_app (COM connection to CST)
- [ ] Test CST.exe launch & close
- [ ] Implement vba_executor (injection via add_to_history)
- [ ] Create VBA macro templates (`templates/cmd_*.vba`)
- [ ] Implement command_parser (validate commands)
- [ ] Implement vba_generator (template substitution)
- [ ] Implement basic execution_engine (sequential execution)
- [ ] Add error handling for COM failures
- [ ] Test with sample command package

**Deliverables**:
- Can launch/control CST via COM
- Can inject VBA macros
- Can execute simple commands (create_project, set_units)
- Error logging for COM issues

**Output Files**:
```
cst/
├── __init__.py
├── cst_app.py (new)
├── vba_executor.py (new)
├── project_manager.py (new)
└── __pycache__/

executor/
├── __init__.py
├── command_parser.py (new)
├── vba_generator.py (new)
├── execution_engine.py (new)
└── templates/
    ├── cmd_create_project.vba
    ├── cmd_set_units.vba
    ├── cmd_define_material.vba
    ├── cmd_create_substrate.vba
    └── ... (9 more templates)
```

---

### **Phase 4: Measurement Extraction (Weeks 7-8)**
**Goal**: Parse CST results, extract S11 data, handle exports

**Tasks**:
- [ ] Implement result_extractor (S11 data parsing)
- [ ] Add touch frequency, bandwidth calculation
- [ ] Extract VSWR, return loss from results
- [ ] Handle CSV/TXT export from CST
- [ ] Implement regex patterns for S-parameter files
- [ ] Add validation for extracted metrics
- [ ] Implement progress_tracker (per-command status)
- [ ] Add export capability (design to JSON/CSV)

**Deliverables**:
- Can extract accurate S11 measurements
- Can calculate center frequency & bandwidth
- Can export design + results
- Progress display during execution

**Output Files**:
```
cst/
├── result_extractor.py (new)
└── export_handler.py (new)

executor/
└── progress_tracker.py (new)

session/
└── design_exporter.py (new)
```

---

### **Phase 5: Feedback Loop & Iteration (Weeks 9-10)**
**Goal**: Handle server feedback, refinement, multi-iteration flows

**Tasks**:
- [ ] Implement response_handler for auto_iterate mode
- [ ] Add iteration tracking in session_store
- [ ] Implement acceptance evaluation logic (local)
- [ ] Handle max_iterations limit
- [ ] Add convergence detection
- [ ] Implement pause/resume execution
- [ ] Add iteration history visualization
- [ ] Enable design comparison (iteration N vs N+1)

**Deliverables**:
- Full feedback loop working
- Multi-iteration designs
- Convergence detection
- Iteration history browsing

**Output Files**:
```
session/
├── iteration_tracker.py (new)
└── design_history.py (expanded)

ui/
├── history_panel.py (new)
└── iteration_viewer.py (new)
```

---

### **Phase 6: Error Recovery & Polish (Weeks 11-12)**
**Goal**: Resilience, user experience, production readiness

**Tasks**:
- [ ] Implement error_recovery (handle network timeouts, CST crashes)
- [ ] Add config_manager (server URL, timeouts, preferences)
- [ ] Implement session persistence (save/restore state)
- [ ] Add help dialogs & tooltips
- [ ] Create user documentation
- [ ] Add performance monitoring (execution times)
- [ ] Implement auto-reconnect to server
- [ ] Create installer (NSIS or MSI)
- [ ] Add telemetry/analytics (optional)

**Deliverables**:
- Production-ready application
- Automatic error recovery
- Configuration GUI
- User manual + video tutorials
- Windows installer

**Output Files**:
```
session/
├── error_recovery.py (new)
└── checkpoint_manager.py (new)

ui/
├── settings_dialog.py (new)
├── help_window.py (new)
└── about_dialog.py (new)

docs/
├── USER_GUIDE.md (new)
├── TROUBLESHOOTING.md (new)
└── API_REFERENCE.md (new)

installer/
├── setup.nsi (NSIS script)
└── build_installer.py (new)
```

---

## Modular API Contracts

### **Internal Module Interfaces**

#### **UI ↔ Session**
```python
# session/session_store.py
class SessionStore:
    def create_session(self, session_id: str, user_request: str) -> dict
    def update_session_status(self, session_id: str, status: str) -> None
    def store_command_package(self, session_id: str, pkg: dict) -> None
    def get_session(self, session_id: str) -> dict
    def list_sessions(self) -> list[dict]
```

#### **Session ↔ Communication**
```python
# comm/api_client.py
class ApiClient:
    async def optimize(self, request: OptimizeRequest) -> OptimizeResponse
    async def send_feedback(self, feedback: dict) -> dict
    async def chat(self, message: str, context: dict) -> str
    async def health_check(self) -> bool
```

#### **Session ↔ Executor**
```python
# executor/execution_engine.py
class ExecutionEngine:
    async def execute_command_package(self, pkg: dict) -> ExecResult
    async def pause_execution(self) -> None
    async def resume_execution(self) -> None
    def get_progress(self) -> dict  # {"total": 10, "completed": 3, "current": 4}
```

#### **Executor ↔ CST**
```python
# cst/cst_app.py
class CSTApp:
    def connect(self) -> bool
    def create_project(self, name: str) -> str
    def execute_macro(self, macro_code: str) -> bool
    def get_project_path(self) -> str
    def close_project(self, save: bool = False) -> None

# cst/result_extractor.py
class ResultExtractor:
    def extract_s11(self, project_path: str) -> dict
    def extract_metrics(self, project_path: str) -> dict
```

---

## Configuration Schema

**`config.json`** (template):
```json
{
  "server": {
    "base_url": "http://192.168.1.100:8000",
    "timeout_sec": 60,
    "retry_count": 3,
    "retry_backoff": 2.0
  },
  "cst": {
    "executable_path": "C:\\Program Files\\CST Studio Suite 2024\\CST Studio.exe",
    "project_dir": "C:\\Users\\<user>\\Documents\\CST Projects",
    "default_units": "mm",
    "frequency_units": "ghz",
    "auto_save": true,
    "save_interval_sec": 300
  },
  "ui": {
    "theme": "dark",
    "default_width": 1200,
    "default_height": 800,
    "auto_connect": true,
    "show_advanced": false
  },
  "logging": {
    "level": "INFO",
    "max_file_size_mb": 10,
    "backup_count": 5,
    "log_dir": "logs"
  },
  "client_capabilities": {
    "supports_farfield_export": true,
    "supports_current_distribution_export": true,
    "max_simulation_timeout_sec": 600,
    "export_formats": ["json", "csv"]
  }
}
```

---

## File Structure (Complete)

```
antenna_client/
├── main.py                          # Entry point
├── config.json                      # Configuration template
├── requirements.txt                 # Python dependencies
├── README.md                        # Project documentation
├── ARCHITECTURE.md                  # This file
│
├── ui/                              # UI Layer
│   ├── __init__.py
│   ├── main_window.py               # Main application window
│   ├── chat_widget.py               # Chat interface
│   ├── design_panel.py              # Design specs panel
│   ├── session_panel.py             # Session history panel
│   ├── status_bar.py                # Status indicator
│   ├── styles.qss                   # PyQt6 stylesheet
│   └── dialogs.py                   # Modal dialogs
│
├── comm/                            # Communication Layer
│   ├── __init__.py
│   ├── server_connector.py          # HTTP client
│   ├── api_client.py                # REST API wrappers
│   ├── request_builder.py           # Request construction
│   ├── response_handler.py          # Response parsing
│   └── intent_parser.py             # Local NLP fallback
│
├── session/                         # State Management Layer
│   ├── __init__.py
│   ├── session_store.py             # Session CRUD
│   ├── chat_history.py              # Chat persistence
│   ├── design_store.py              # Design storage
│   ├── design_history.py            # Version tracking
│   ├── design_exporter.py           # Export to JSON/CSV
│   ├── iteration_tracker.py         # Iteration metadata
│   ├── config_manager.py            # Configuration
│   ├── checkpoint_manager.py        # Execution checkpoints
│   └── error_recovery.py            # Error handling
│
├── cst/                             # CST Interface Layer
│   ├── __init__.py
│   ├── cst_app.py                   # COM connection
│   ├── vba_executor.py              # VBA injection
│   ├── project_manager.py           # Project lifecycle
│   ├── result_extractor.py          # Results parsing
│   └── export_handler.py            # Export management
│
├── executor/                        # Command Execution Layer
│   ├── __init__.py
│   ├── command_parser.py            # Command validation
│   ├── vba_generator.py             # VBA generation
│   ├── execution_engine.py          # Orchestration
│   ├── progress_tracker.py          # Progress tracking
│   └── templates/                   # VBA macro templates
│       ├── cmd_create_project.vba
│       ├── cmd_set_units.vba
│       ├── cmd_set_frequency_range.vba
│       ├── cmd_define_material.vba
│       ├── cmd_create_substrate.vba
│       ├── cmd_create_ground_plane.vba
│       ├── cmd_create_patch.vba
│       ├── cmd_create_feedline.vba
│       ├── cmd_create_port.vba
│       ├── cmd_run_solver.vba
│       └── cmd_export_s11.vba
│
├── utils/                           # Utilities
│   ├── __init__.py
│   ├── logger.py                    # Structured logging
│   ├── constants.py                 # Constants & defaults
│   ├── validators.py                # Schema validation
│   └── decorators.py                # Reusable decorators
│
├── docs/                            # Documentation
│   ├── USER_GUIDE.md
│   ├── TROUBLESHOOTING.md
│   ├── API_REFERENCE.md
│   └── DEVELOPER_GUIDE.md
│
├── tests/                           # Test suite
│   ├── __init__.py
│   ├── test_api_client.py
│   ├── test_command_parser.py
│   ├── test_vba_generator.py
│   ├── test_result_extractor.py
│   └── integration/
│       ├── test_full_pipeline.py
│       └── test_server_integration.py
│
├── logs/                            # Runtime logs (created)
│   └── antenna_client.log
│
├── data/                            # Persisted data (created)
│   ├── sessions.db                  # SQLite session store
│   ├── designs.db                   # Design history
│   └── cache/                       # Temporary files
│
├── installer/                       # Windows installer
│   ├── setup.nsi                    # NSIS script
│   └── build_installer.py
│
└── .gitignore
```

---

## Dependencies

### **Core Requirements** (`requirements.txt`)
```
PyQt6==6.6.1                    # UI framework
httpx==0.27.2                   # Async HTTP client
pydantic==2.11.10              # Schema validation
pywin32==306                   # Windows COM interface
python-dotenv==1.0.1           # Environment config
pytest==8.3.3                  # Testing
pytest-asyncio==0.24.0         # Async test support
```

### **Optional Dependencies**
```
# Light theme alternative
PySimpleGUI==4.61.0

# Performance monitoring
psutil==6.0.0

# Analytics (optional)
sentry-sdk==1.49.0
```

---

## Deployment & Setup

### **Development Setup**
```bash
git clone <repo>
cd antenna_client
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### **Production Setup (Installer)**
1. User downloads `antenna_client_installer.exe`
2. Installer:
   - Installs Python 3.10+ (if missing)
   - Extracts application to `C:\Program Files\AntennaClient`
   - Creates Start Menu shortcuts
   - Sets up config.json with CST path detection
   - Creates scheduled task for log cleanup
3. User runs app from Start Menu
4. Prompts for server URL on first run

---

## Key Design Principles

1. **Modularity**: Each layer has single responsibility; loose coupling
2. **Async-First**: Non-blocking UI, async HTTP calls
3. **Offline Fallback**: Local intent parser if server unavailable
4. **Error Resilience**: Graceful handling of network/CST failures
5. **Transparency**: Detailed logging of all operations
6. **Testability**: Dependency injection, mockable interfaces
7. **Performance**: Lazy loading, caching where appropriate
8. **User Experience**: Responsive UI, progress indication, clear error messages

---

## Success Criteria

### **Phase 1 (Foundation)**
- ✓ Project builds & runs without errors
- ✓ Can connect to antenna_server
- ✓ Can send/receive JSON correctly
- ✓ Unit test coverage ≥ 80%

### **Phase 2 (Chat)**
- ✓ Chat interface responsive
- ✓ Intent parsing 90%+ accurate (regex-based)
- ✓ Can handle multi-turn conversations
- ✓ Graceful offline mode

### **Phase 3 (CST)**
- ✓ Can launch/close CST reliably
- ✓ Can inject VBA without crashes
- ✓ Commands execute in correct order
- ✓ COM error handling robust

### **Phase 4 (Measurements)**
- ✓ Extract S11 data with <0.1% error
- ✓ Calculate bandwidth accurately
- ✓ Handle missing export files gracefully

### **Phase 5 (Iteration)**
- ✓ Multi-iteration designs converge
- ✓ Can iterate 5+ times without crashes
- ✓ History browsing fast (<100ms)

### **Phase 6 (Production)**
- ✓ Installer installs cleanly
- ✓ App recovers from 95%+ of errors automatically
- ✓ User documentation 100% complete
- ✓ No crashes in 1 hour continuous operation

---

## Future Enhancements (Post-MVP)

1. **Real-time Streaming**: WebSocket for live progress updates
2. **Parameter Sweep**: Ability to sweep frequency/bandwidth ranges
3. **Batch Operations**: Design multiple antennas in queue
4. **Remote CST**: Execute CST on remote Windows machine
5. **ML-Assisted Refinement**: Local lightweight model for intelligent refinement suggestions
6. **Design Comparison**: Visual diff between iterations
7. **Measurement Units**: Support mm/inches/cm/wavelengths
8. **Export Formats**: STEP, STL for 3D printing
9. **Collaboration**: Share designs via cloud storage
10. **Hardware Optimization**: GPU acceleration for large datasets

---

**Document Version**: 1.0  
**Last Updated**: 2026-04-02  
**Status**: Architecture Plan (Ready for Phase 1 Implementation)
