# Antenna Client — Architecture & Developer Reference

> **Version:** 0.1.0 | **Stack:** Python 3.10, PySide6, httpx, websockets, Pydantic, CST Python API

---

## Table of Contents

1. [Overview](#1-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Complete File Structure](#3-complete-file-structure)
4. [Layer-by-Layer Description](#4-layer-by-layer-description)
   - [4.1 Entry Point](#41-entry-point)
   - [4.2 UI Layer](#42-ui-layer)
   - [4.3 Communication Layer](#43-communication-layer)
   - [4.4 CST Client Layer](#44-cst-client-layer)
   - [4.5 Executor Layer](#45-executor-layer)
   - [4.6 Session Layer](#46-session-layer)
   - [4.7 Tools Layer](#47-tools-layer)
   - [4.8 Utils Layer](#48-utils-layer)
5. [Client ↔ Server Communication](#5-client--server-communication)
   - [5.1 REST API Endpoints](#51-rest-api-endpoints)
   - [5.2 WebSocket Stream](#52-websocket-stream)
   - [5.3 Request/Response Data Flow](#53-requestresponse-data-flow)
   - [5.4 Error Codes & Recovery](#54-error-codes--recovery)
6. [CST Implementation Logic](#6-cst-implementation-logic)
   - [6.1 Connection Strategy](#61-connection-strategy)
   - [6.2 VBA Macro Pipeline](#62-vba-macro-pipeline)
   - [6.3 VBA Template Library](#63-vba-template-library)
   - [6.4 Execution Engine Internals](#64-execution-engine-internals)
   - [6.5 Result Extraction](#65-result-extraction)
7. [End-to-End Workflow](#7-end-to-end-workflow)
8. [Configuration](#8-configuration)
9. [Data Models](#9-data-models)
10. [Design Decisions & Patterns](#10-design-decisions--patterns)

---

## 1. Overview

The **Antenna Client** is a desktop GUI application that lets engineers design microstrip patch antennas (and AMC/WBAN variants) through a conversational interface. It connects to a remote **antenna_server** (an AI/ML backend) over HTTP/WebSocket, receives structured CST command packages, and drives **CST Studio Suite** locally to build, simulate, and extract results — all without manual CST interaction.

```
User Prompt ──► Antenna Client (this repo) ──► antenna_server (AI/ML)
                        │                              │
                        │   CST Command Package        │
                        │◄─────────────────────────────┘
                        │
                        ▼
              CST Studio Suite (local)
              (VBA macros injected via Python API)
```

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         UI LAYER (PySide6)                       │
│   MainWindow ◄──► ChatWidget ◄──► DesignPanel ◄──► StatusBar    │
└────────────────────────────┬────────────────────────────────────┘
                             │ Qt Signals / QThread workers
┌────────────────────────────▼────────────────────────────────────┐
│                    UTILS / ORCHESTRATION                         │
│   ChatMessageHandler  │  HealthMonitor  │  ConnectionChecker     │
└──────┬─────────────────────────┬────────────────────────────────┘
       │ asyncio / httpx          │ asyncio / httpx
┌──────▼──────────────┐   ┌──────▼──────────────────────────────┐ │
│  COMM LAYER         │   │       COMM LAYER                     │ │
│  ServerConnector    │   │       ws_client                      │ │
│  ApiClient          │   │       SessionEventListener           │ │
│  RequestBuilder     │   └──────────────────────────────────────┘ │
│  ResponseHandler    │                                             │
│  ErrorHandler       │                                             │
│  IntentParser       │                                             │
└──────┬──────────────┘                                             │
       │ OptimizeResponse / CommandPackage                          │
┌──────▼──────────────────────────────────────────────────────────┐
│                    EXECUTOR LAYER                                 │
│   CommandParser  ──►  ExecutionEngine  ──►  VBAGenerator         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ VBA macro strings
┌──────────────────────────▼──────────────────────────────────────┐
│                    CST CLIENT LAYER                               │
│   CSTApp  ──►  cst.interface.DesignEnvironment  (Windows API)    │
│   VBAExecutor     ProjectManager     ResultExtractor             │
└──────────────────────────┬──────────────────────────────────────┘
                           │ exec result / exported files
┌──────────────────────────▼──────────────────────────────────────┐
│                    SESSION LAYER                                  │
│   SessionStore  CheckpointManager  DesignStore  DesignExporter   │
│   ChatHistory   IterationTracker   ConfigManager  ErrorRecovery  │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│                    TOOLS LAYER (offline calc)                    │
│   RectangularPatchCalculator  AMCCalculator  WBANCalculator      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Complete File Structure

```
antenna_client/
│
├── config.json                    ← Runtime configuration (server URL, CST path, UI prefs)
├── main.py                        ← Alternate top-level launcher (delegates to src/main.py)
├── requirements.txt               ← Python dependencies
├── pyrightconfig.json             ← Type-checking config
│
├── src/                           ← All source code lives here
│   ├── main.py                    ← Application entry point (launches PySide6 app)
│   │
│   ├── comm/                      ← Server communication layer
│   │   ├── __init__.py
│   │   ├── antenna_commands.py    ← Pydantic models for per-family optimize commands
│   │   ├── api_client.py          ← High-level REST wrapper (optimize/chat/result/health)
│   │   ├── error_handler.py       ← Error code enum + user-friendly message mapping
│   │   ├── initializer.py         ← Startup sequence: health poll → capabilities load
│   │   ├── intent_parser.py       ← Local NLP fallback (offline mode)
│   │   ├── request_builder.py     ← Builds OptimizeRequest Pydantic model
│   │   ├── response_handler.py    ← Parses OptimizeResponse; handles all server statuses
│   │   ├── server_connector.py    ← Async httpx client with retry + backoff
│   │   └── ws_client.py           ← WebSocket session event streaming
│   │
│   ├── cst_client/                ← CST Studio integration
│   │   ├── __init__.py
│   │   ├── cst_app.py             ← Main CST wrapper: connect, create project, execute macro
│   │   ├── project_manager.py     ← Project lifecycle (create/open/save CST projects)
│   │   ├── result_extractor.py    ← Parse exported S11/CSV files, compute metrics
│   │   └── vba_executor.py        ← Low-level VBA injection helpers
│   │
│   ├── executor/                  ← Command package execution pipeline
│   │   ├── __init__.py
│   │   ├── command_parser.py      ← Parse + validate CommandPackage from server
│   │   ├── execution_engine.py    ← Orchestrate sequential command execution in CST
│   │   ├── progress_tracker.py    ← Track and emit execution progress
│   │   ├── v2_command_contract.py ← Strict v2 schema validator (from JSON contract file)
│   │   ├── vba_generator.py       ← Convert command dicts → VBA macro strings
│   │   └── templates/             ← Per-command VBA template files (.vba)
│   │       ├── cmd_create_project.vba
│   │       ├── cmd_create_substrate.vba
│   │       ├── cmd_create_patch.vba
│   │       ├── cmd_create_feedline.vba
│   │       ├── cmd_create_ground_plane.vba
│   │       ├── cmd_create_port.vba
│   │       ├── cmd_define_material.vba
│   │       ├── cmd_define_parameter.vba
│   │       ├── cmd_update_parameter.vba
│   │       ├── cmd_define_brick.vba
│   │       ├── cmd_define_sphere.vba
│   │       ├── cmd_define_cone.vba
│   │       ├── cmd_define_cylinder.vba
│   │       ├── cmd_define_ecylinder.vba
│   │       ├── cmd_define_extrude.vba
│   │       ├── cmd_define_loft.vba
│   │       ├── cmd_define_torus.vba
│   │       ├── cmd_define_rotate.vba
│   │       ├── cmd_boolean_add.vba
│   │       ├── cmd_boolean_subtract.vba
│   │       ├── cmd_boolean_intersect.vba
│   │       ├── cmd_boolean_insert.vba
│   │       ├── cmd_set_frequency_range.vba
│   │       ├── cmd_set_units.vba
│   │       ├── cmd_create_component.vba
│   │       ├── cmd_calculate_port_extension_coefficient.vba
│   │       ├── cmd_pick_face.vba
│   │       ├── cmd_pick_edge.vba
│   │       ├── cmd_pick_endpoint.vba
│   │       ├── cmd_rebuild_model.vba
│   │       ├── cmd_run_solver.vba
│   │       └── cmd_export_s11.vba
│   │
│   ├── session/                   ← Session and state management
│   │   ├── __init__.py
│   │   ├── session_store.py       ← In-memory + file-backed session CRUD
│   │   ├── checkpoint_manager.py  ← Save/restore execution checkpoints for recovery
│   │   ├── design_store.py        ← Store antenna design specs by ID
│   │   ├── design_exporter.py     ← Export designs to JSON / CSV
│   │   ├── chat_history.py        ← Persist conversation history
│   │   ├── config_manager.py      ← Load/save config.json
│   │   ├── error_recovery.py      ← Error recovery strategies
│   │   └── iteration_tracker.py   ← Track optimize→simulate→feedback iterations
│   │
│   ├── tools/                     ← Local (offline) antenna calculators
│   │   ├── prepare_offline_feedback.py  ← Prepare feedback payload without server
│   │   └── antenna_calculations/
│   │       ├── __init__.py
│   │       ├── rect_patch_calculator.py ← Rectangular patch formulas (Hammerstad model)
│   │       ├── amc_calculator.py        ← AMC unit cell + array dimension calculator
│   │       └── wban_calculator.py       ← WBAN-specific patch calculator
│   │
│   ├── ui/                        ← PySide6 UI components
│   │   ├── __init__.py
│   │   ├── main_window.py         ← QMainWindow: layout, menus, shortcuts, worker threads
│   │   ├── chat_widget.py         ← Chat conversation view + text input
│   │   ├── design_panel.py        ← Antenna family / freq / material form controls
│   │   ├── status_bar.py          ← Connection status, progress indicators
│   │   └── styles.qss             ← Qt stylesheet (light/dark theme)
│   │
│   └── utils/                     ← Shared utilities
│       ├── __init__.py
│       ├── chat_message_handler.py ← UI workflow controller: QThread workers for all ops
│       ├── connection_checker.py   ← Async server + CST availability checker
│       ├── constants.py            ← App-wide constants and defaults
│       ├── health_monitor.py       ← Periodic (30s) health check worker
│       ├── logger.py               ← Rotating file + console logger setup
│       ├── material_resolver.py    ← Single-source material resolution priority chain
│       └── validators.py          ← Pydantic validators, family alias mapping
│
├── config/
│   └── schema/
│       └── cst_command_package.v2.command_contract.json  ← V2 command schema registry
│
├── artifacts/                     ← Auto-generated CST exports
│   └── exports/                   ← S11 CSV, farfield exports
│
├── test_checkpoints/              ← Persisted session JSON files (auto-saved)
├── logs/                          ← Rotating log files
├── scripts/                       ← Standalone diagnostic / integration scripts
└── tests/                         ← Unit and integration tests
```

---

## 4. Layer-by-Layer Description

### 4.1 Entry Point

**File:** `src/main.py`

Boots the PySide6 `QApplication`, instantiates `MainWindow`, and enters the Qt event loop.

```python
app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())
```

---

### 4.2 UI Layer

**Directory:** `src/ui/`

| File | Class | Responsibility |
|------|-------|---------------|
| `main_window.py` | `MainWindow` | Top-level `QMainWindow`. Owns layout (splitter: chat left, design panel right). Spawns `InitializationWorker` and `ConnectionWorker` QThreads on startup. |
| `chat_widget.py` | `ChatWidget` | Scrollable conversation pane + text input. Emits `message_submitted` signal on Enter. |
| `design_panel.py` | `DesignPanel` | Form controls: antenna family combo, frequency/bandwidth spinboxes, material dropdowns. Emits `design_changed`, `start_pipeline_requested`, `export_requested`. |
| `status_bar.py` | `AppStatusBar` | Shows server connectivity status, ANN/LLM status, and progress messages. |
| `styles.qss` | — | Qt stylesheet for light/dark theming. |

**Worker Threads in `main_window.py`:**

| Worker | Purpose |
|--------|---------|
| `InitializationWorker` | Async: GET `/api/v1/health` → GET `/api/v1/capabilities` at startup |
| `ConnectionWorker` | Async: quick server + CST connectivity snapshot |

These workers run `asyncio` event loops in background `QThread`s to avoid blocking the Qt GUI thread.

---

### 4.3 Communication Layer

**Directory:** `src/comm/`

#### `server_connector.py` — `ServerConnector`

The HTTP transport layer. Uses **`httpx.AsyncClient`** with:
- Connection pooling (max 10 connections, 5 keepalive)
- Configurable timeout (default 60s)
- Exponential backoff retry (default 3 retries)

```python
async with ServerConnector("http://192.168.234.112:8000") as connector:
    data = await connector.get("/api/v1/health")
    data = await connector.post("/api/v1/optimize", json=request_dict)
```

#### `api_client.py` — `ApiClient`

Wraps `ServerConnector` with business-level methods:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `optimize()` | `POST /api/v1/optimize` | Send design request, receive CommandPackage |
| `chat()` | `POST /api/v1/chat` | Conversational assistant guidance |
| `parse_intent()` | `POST /api/v1/intent/parse` | Extract structured intent from free text |
| `send_result()` | `POST /api/v1/result` | Post CST simulation results back to server |
| `send_feedback()` | alias → `send_result()` | Backward-compatible alias |
| `get_session()` | `GET /api/v1/sessions/{id}` | Fetch session state |
| `load_capabilities()` | `GET /api/v1/capabilities` | Get server capability catalog |
| `health_check()` | `GET /api/v1/health` | Server + AI model status |

#### `request_builder.py` — `RequestBuilder`

Constructs the `OptimizeRequest` Pydantic model from:
1. User free-text (`user_request`)
2. Design panel form values (frequency, bandwidth, family, materials)
3. Client capability declarations

Key field: `schema_version: "optimize_request.v1"` — must match server schema.

#### `response_handler.py` — `ResponseHandler`, `OptimizeResponse`

Parses server response via Pydantic. Handles all server statuses:

| Status | Action |
|--------|--------|
| `accepted` + command_package | → Execute CST commands |
| `accepted` (no package) | → Wait / notify user |
| `completed` + command_package | → Execute CST commands |
| `clarification_required` | → Show clarification prompt in chat |
| `error` | → Parse error code → user message |

Response carries `ann_prediction` (ANN model dimensions) and `command_package` (CST execution plan).

#### `error_handler.py` — `ErrorHandler`

Maps server error codes to user-friendly messages and recovery actions:

| Error Code | User Action |
|-----------|-------------|
| `SCHEMA_VALIDATION_FAILED` | Retry with corrected form values |
| `FAMILY_NOT_SUPPORTED` | Choose different antenna family |
| `LOW_SURROGATE_CONFIDENCE` | Adjust frequency/bandwidth |
| `SESSION_NOT_FOUND` | Start new session |
| `V2_COMMAND_VALIDATION_FAILED` | Review command package, retry |

#### `ws_client.py` — `SessionEventListener`

WebSocket client connecting to:
```
ws://<server>/api/v1/sessions/{session_id}/stream
```

Supports typed event handlers via `on_event(event_type, async_handler)`. Used to stream live iteration events (e.g., `iteration.completed`) from the server without polling.

#### `initializer.py` — `ClientInitializer`

Implements the startup sequence:
1. `GET /api/v1/health` → check ANN/LLM status
2. Poll health until warm-up completes (if `loading`)
3. `GET /api/v1/capabilities` → populate capability catalog
4. Emit progress events to UI

#### `intent_parser.py` — `IntentParser`

Local NLP fallback when server is offline. Uses regex to extract:
- Frequency (GHz/MHz), Bandwidth, Antenna type, Action verb

---

### 4.4 CST Client Layer

**Directory:** `src/cst_client/`

#### `cst_app.py` — `CSTApp`

The core CST integration class. Uses the official **CST Python API** (`cst.interface`).

```python
import cst.interface
self.app = cst.interface.DesignEnvironment.connect_to_any_or_new()
self.project = self.app.active_project()
self.mws = self.project.model3d  # MWS handle for VBA injection
```

Key methods:

| Method | What it does |
|--------|-------------|
| `connect()` | Attaches to running CST DE or launches a new one (Windows-only) |
| `create_project(name)` | Creates new `.cst` MWS project, saves to `project_dir` |
| `open_project(path)` | Opens existing `.cst` file |
| `execute_macro(vba_code, title)` | Injects VBA as a history entry and triggers `full_history_rebuild()` |
| `export_farfield(path)` | Export farfield pattern to file |
| `export_s_parameters(path)` | Export S-parameters to file |

**Resilience:** `execute_macro` auto-retries once — on the first attempt if `mws` is `None` it calls `connect()` + `_refresh_active_project()` before giving up.

#### `vba_executor.py` — `VBAExecutor`

Higher-level helper wrapping `CSTApp`. Provides convenience methods:
- `define_material(name, epsilon_r, loss_tangent)`
- `create_rectangle(name, x_min..z_max, material)`
- `execute_macro(code)` — delegates to `CSTApp`

#### `project_manager.py` — `ProjectManager`

Handles project file lifecycle:
- `create_project(name)` — creates directory + CST project
- `open_project(path)` — opens `.cst` file in CST
- `save_project()`, `close_project()`

#### `result_extractor.py` — `ResultExtractor`

Parses CST exported files after simulation:
- `extract_s11(file)` — reads S11 CSV/TXT → frequency + S11 lists
- `extract_metrics(s11_data)` → center frequency, bandwidth, VSWR, return loss, gain
- `find_center_frequency(freqs, s11_db)` — minimum S11 point
- `calculate_bandwidth(freqs, s11_db, threshold=-10dB)` — -10 dB bandwidth
- `calculate_vswr(s11_linear)` — VSWR from S11

---

### 4.5 Executor Layer

**Directory:** `src/executor/`

#### `command_parser.py` — `CommandParser`, `CommandPackage`, `Command`

Parses the server's `cst_command_package` JSON. Pydantic models:

```
CommandPackage
├── schema_version: "cst_command_package.v1" or ".v2"
├── session_id, trace_id, design_id, iteration_index
├── units: {geometry: "mm", frequency: "GHz"}
├── predicted_dimensions: {patch_length_mm, substrate_height_mm, ...}
├── commands: List[Command]
│   └── Command: {seq, command, params, on_failure, checksum_scope}
└── expected_exports: ["s11", "farfield"]
```

`on_failure` can be `"abort"` or `"retry_once"` — controls execution engine behavior.

Supports both v1 (field alias `type`/`parameters`) and v2 strict command names.

#### `v2_command_contract.py` — `V2CommandContractValidator`

For `schema_version: "cst_command_package.v2"` packages, validates against:
- `config/schema/cst_command_package.v2.command_contract.json`
- Checks: strictly increasing `seq`, known command names, required params for geometry/simulation commands, `rebuild_model` appears before simulation commands

#### `vba_generator.py` — `VBAGenerator`

Translates a `Command` dict into a VBA macro string. Two strategies:

1. **Template-based:** Loads `.vba` file from `executor/templates/`, substitutes `{{param}}` placeholders with command params.
2. **Inline hardcoded:** For materials with known profiles (Gold, Silver, Rogers RO3003, FR-4, Copper, etc.), generates complete `With Material ... End With` VBA blocks with all physical properties pre-filled.

Material profile logic normalizes names (`_` → space, strip `(lossy)`) and matches against known profiles. Unknown materials fall back to simple epsilon/tan-delta definition.

#### `execution_engine.py` — `ExecutionEngine`

The orchestration core. For each `Command` in sequence:

```
for command in package.commands:
    1. Generate VBA via VBAGenerator
    2. Apply material resolution (stamp conductor/substrate names)
    3. CSTApp.execute_macro(vba_code)   ← Windows CST API call
    4. Record ExecutionResult (success/error/macro text)
    5. If on_failure == "retry_once": retry once on failure
    6. If on_failure == "abort": break on failure
```

Maintains execution context:
- `_geometry_context` — tracks created shapes and positions
- `_parameter_context` — tracks CST parametric variables  
- `_material_context` — tracks defined materials to avoid redefinition
- `_scoped_hint_cache` — artifact file path naming

When `CSTApp.connect()` fails (CST not available), sets `dry_run = True` and skips actual CST calls — useful for testing.

---

### 4.6 Session Layer

**Directory:** `src/session/`

| File | Class | Purpose |
|------|-------|---------|
| `session_store.py` | `SessionStore` | In-memory `dict[session_id → Session]` + JSON persistence to `test_checkpoints/`. Loads all `.json` files on startup. |
| `checkpoint_manager.py` | `CheckpointManager` | Save/restore execution state to `checkpoints/{session_id}_checkpoint.json`. Cleanup policy: delete files older than 24h. |
| `design_store.py` | `DesignStore` | Store and retrieve `Design` objects (specs + iteration history) by ID. |
| `design_exporter.py` | `DesignExporter` | Export design dicts to JSON or CSV files. |
| `chat_history.py` | `ChatHistory` | Append and retrieve conversation messages. |
| `config_manager.py` | `ConfigManager` | Load and update `config.json` at runtime. |
| `error_recovery.py` | `ErrorRecovery` | Recovery strategies when execution fails. |
| `iteration_tracker.py` | `IterationTracker` | Track which optimize→simulate→feedback cycle the session is on. |

**Session persistence flow:**
```
SessionStore.create_session()
    → Session object in memory
    → Saved as test_checkpoints/{session_id}.json
    → Reloaded on next app start
```

---

### 4.7 Tools Layer

**Directory:** `src/tools/antenna_calculations/`

Local calculators for offline dimension estimation (no server required):

| Calculator | Implements |
|-----------|-----------|
| `RectangularPatchCalculator` | Hammerstad effective dielectric model; patch width/length from frequency + substrate; feed width from target impedance; bandwidth estimate |
| `AMCCalculator` | AMC unit cell period/patch size from frequency + substrate epsilon; array grid sizing; reflection phase bandwidth estimate |
| `WBANCalculator` | Body-worn antenna patch sizing accounting for tissue loading |

These are used by `prepare_offline_feedback.py` to generate a local feedback payload when the server is unavailable.

---

### 4.8 Utils Layer

**Directory:** `src/utils/`

| File | Purpose |
|------|---------|
| `chat_message_handler.py` | **Central workflow controller.** All QThread worker classes: `ChatRequestWorker`, `OptimizeWorker`, `ExecutionWorker`, `FeedbackWorker`, `ResetWorker`, `ExportWorker`. Bridges UI signals to async backend operations. |
| `connection_checker.py` | `ConnectionChecker.check_all()` — parallel async check of server health + CST availability. Returns structured dict for status bar. |
| `constants.py` | App-wide constants: `APP_NAME`, `APP_VERSION`, default URLs, CST exe path, UI dimensions. |
| `health_monitor.py` | `HealthMonitorWorker` (QThread polling every 30s) + `HealthMonitor` manager. Updates status bar on connectivity change. |
| `logger.py` | Rotating file logger (`logs/`) + console handler. Returns `logging.Logger` via `get_logger(__name__)`. |
| `material_resolver.py` | **Single authority for material names.** `resolve_materials()` with priority chain: UI form → server response → command package → family default. `normalize_material_name()` canonicalizes strings. |
| `validators.py` | `extract_frequency_bandwidth()`, `extract_antenna_family()`, FAMILY_ALIASES map, Pydantic `DesignSpecification` model. |

---

## 5. Client ↔ Server Communication

### 5.1 REST API Endpoints

All requests go to `http://<server_ip>:8000` (configured in `config.json`).

```
GET  /api/v1/health
     Response: {status: "ok", ann_status: "ready", llm_status: "ready", ...}

GET  /api/v1/capabilities
     Response: capability catalog for the server's supported antenna families and features

POST /api/v1/intent/parse
     Body:    {user_request: "design a 2.4 GHz patch"}
     Response:{intent_summary: {frequency_ghz, bandwidth_mhz, antenna_family, ...}}

POST /api/v1/chat
     Body:    {message: str, requirements: dict}
     Response:{assistant_reply: str, intent_summary: dict, ...}

POST /api/v1/optimize                     ← Main design pipeline trigger
     Body:    OptimizeRequest (JSON)
     Response:OptimizeResponse (JSON)

POST /api/v1/result                       ← Return CST simulation results to server
     Body:    {session_id, metrics: {s11_db, bandwidth_mhz, ...}, artifacts: {s11_path, ...}}
     Response:{status, next_action, ...}
```

### 5.2 WebSocket Stream

```
WS ws://<server_ip>:8000/api/v1/sessions/{session_id}/stream
```

The server pushes `session.event` JSON frames:
```json
{"event_type": "iteration.completed", "iteration": 1, "metrics": {...}}
{"event_type": "optimization.converged", "final_design": {...}}
{"event_type": "error", "code": "...", "message": "..."}
```

`SessionEventListener.on_event(event_type, handler)` registers per-event-type async callbacks.

### 5.3 Request/Response Data Flow

```
User types message
        │
        ▼
ChatWidget.message_submitted signal
        │
        ▼
ChatMessageHandler  ──► spawns ChatRequestWorker (QThread)
        │                        │
        │                        ├── POST /api/v1/chat
        │                        └── POST /api/v1/intent/parse  (parallel asyncio.gather)
        │
        ▼  (requirements extracted from intent)
User clicks "Start Pipeline" / auto-trigger
        │
        ▼
ChatMessageHandler ──► spawns OptimizeWorker (QThread)
        │                        │
        │                        ├── RequestBuilder.build_optimize_request()
        │                        │     └── OptimizeRequest {schema_version, user_request,
        │                        │          target_spec, design_constraints,
        │                        │          optimization_policy, runtime_preferences,
        │                        │          client_capabilities, session_id}
        │                        │
        │                        └── POST /api/v1/optimize
        │                                │
        │                                ▼
        │                        OptimizeResponse {
        │                            status: "accepted",
        │                            session_id: "abc",
        │                            ann_prediction: {dimensions: {...}},
        │                            command_package: {
        │                                schema_version: "cst_command_package.v2",
        │                                commands: [
        │                                    {seq:1, command:"create_project", params:{...}},
        │                                    {seq:2, command:"set_units", params:{...}},
        │                                    {seq:3, command:"define_material", params:{...}},
        │                                    ...
        │                                    {seq:N, command:"run_solver", params:{}}
        │                                ]
        │                            }
        │                        }
        │
        ▼
CommandParser.parse_package()
        │
        ▼
ExecutionEngine.execute_command_package()
        │   (for each Command in sequence)
        ├── VBAGenerator.generate(command) → VBA string
        ├── CSTApp.execute_macro(vba)      → CST API call
        └── ExecutionResult recorded
        │
        ▼
ResultExtractor.extract_metrics()
        │
        ▼
ChatMessageHandler ──► spawns FeedbackWorker (QThread)
        │                        │
        │                        └── POST /api/v1/result
        │                               {session_id, metrics, artifacts}
        │
        ▼
Server decides: converged ──► done
                not converged ──► sends new command_package (next iteration)
```

### 5.4 Error Codes & Recovery

| Phase | Failure | Recovery |
|-------|---------|---------|
| HTTP transport | Connection refused / timeout | Exponential backoff retry (3×) |
| Server response | `SCHEMA_VALIDATION_FAILED` | Show form validation hints |
| Server response | `FAMILY_NOT_SUPPORTED` | Prompt family change |
| Server response | `LOW_SURROGATE_CONFIDENCE` | Suggest parameter adjustment |
| Session expired | `SESSION_NOT_FOUND` | Auto-start new session |
| CST not available | `connect()` fails | `dry_run=True` mode (skips VBA calls) |
| VBA execution | CST API exception | `retry_once` if flagged, else abort package |

---

## 6. CST Implementation Logic

### 6.1 Connection Strategy

CST Studio must be running on the **same Windows machine** as the client.

```python
import cst.interface
app = cst.interface.DesignEnvironment.connect_to_any_or_new()
# ↑ Connects to existing DE session OR launches new one
project = app.active_project()
mws = project.model3d  # MWS (Microwave Studio) 3D environment handle
```

On **non-Windows** systems or if `import cst.interface` fails, `CSTApp.connect()` returns `False` and `ExecutionEngine.dry_run` is set to `True`.

### 6.2 VBA Macro Pipeline

CST Studio is driven entirely via **VBA macro injection into the history tree**:

```
Server Command Dict
       │
       ▼  VBAGenerator.generate(command)
VBA macro string  (e.g., With Brick ... .Create ... End With)
       │
       ▼  CSTApp.execute_macro(vba_code, title)
mws.add_to_history("create_patch", vba_code)
mws.full_history_rebuild()
       │
       ▼
CST Studio executes the history entry, updating the 3D model
```

Every operation adds an entry to CST's parametric history. `full_history_rebuild()` forces CST to re-evaluate all history items in order — this is the standard CST automation pattern.

### 6.3 VBA Template Library

**Location:** `src/executor/templates/*.vba`

Templates use `{{placeholder}}` syntax. `VBAGenerator` substitutes runtime values before injection.

Example: `cmd_create_patch.vba`
```vba
With Brick
    .Reset
    .Name "{{patch_name}}"
    .Component "component1"
    .Material "PEC"
    .Xmin {{x_min}}  .Xmax {{x_max}}
    .Ymin {{y_min}}  .Ymax {{y_max}}
    .Zmin {{z_min}}  .Zmax {{z_max}}
    .Create
End With
```

**Supported template commands:**

| Category | Commands |
|----------|---------|
| Project setup | `create_project`, `set_units`, `set_frequency_range` |
| Geometry primitives | `define_brick`, `define_sphere`, `define_cone`, `define_cylinder`, `define_ecylinder`, `define_torus`, `define_extrude`, `define_loft`, `define_rotate` |
| Antenna-specific | `create_substrate`, `create_ground_plane`, `create_patch`, `create_feedline`, `create_port`, `create_component` |
| Boolean ops | `boolean_add`, `boolean_subtract`, `boolean_intersect`, `boolean_insert` |
| Parameters | `define_parameter`, `update_parameter`, `calculate_port_extension_coefficient` |
| Picking | `pick_face`, `pick_edge`, `pick_endpoint` |
| Materials | `define_material` |
| Simulation | `rebuild_model`, `run_solver`, `export_s11` |

### 6.4 Execution Engine Internals

`ExecutionEngine` maintains execution-scoped context dictionaries:

```
_geometry_context   = {}   # shape_name → {x_min, x_max, z_min, ...}
_parameter_context  = {}   # param_name → value
_material_context   = {    
    "defined": [],         # list of already-defined material names
    "by_kind": {}          # conductor/substrate → canonical name
}
_scoped_hint_cache  = {}   # base_hint → scoped artifact filename
```

**Material context** prevents re-defining the same material twice in one package execution. If a material in `_material_context["defined"]` is requested again, the `define_material` command is skipped.

**Artifact naming** is scoped per session: `{session_16chars}_iter{N}_{design_20chars}_{base_hint}.{ext}` — ensuring exports from different iterations never collide.

**Dry-run mode:** when `CSTApp.connect()` returns `False`, every `execute_macro` call is skipped but an `ExecutionResult(success=True, output="[dry-run]")` is returned, allowing the rest of the pipeline (result handling, feedback) to proceed with mock data.

### 6.5 Result Extraction

After `run_solver` completes:

```
CSTApp.export_s_parameters(export_path)
        │
        ▼
ResultExtractor.extract_s11(export_path)
    → parse CSV: frequency_col, s11_db_col
        │
        ▼
ResultExtractor.extract_metrics(s11_data)
    → center_frequency_ghz  (argmin of S11)
    → bandwidth_mhz         (-10 dB crossing points)
    → return_loss_db        (min S11 value)
    → vswr                  (from S11 linear via (1+|S11|)/(1-|S11|))
    → gain_dbi              (from farfield export if available)
        │
        ▼
FeedbackWorker sends metrics to POST /api/v1/result
```

---

## 7. End-to-End Workflow

```
1. STARTUP
   MainWindow.__init__()
   └── InitializationWorker.run()
       ├── GET /api/v1/health  ──► parse ANN/LLM status
       └── GET /api/v1/capabilities  ──► update UI

2. HEALTH MONITOR (background, every 30s)
   HealthMonitorWorker  ──► ConnectionChecker.check_all()
   └── Updates StatusBar with server/CST status

3. USER CHAT
   User types in ChatWidget → Enter
   └── ChatRequestWorker
       ├── POST /api/v1/chat       ←─ parallel asyncio.gather
       └── POST /api/v1/intent/parse
       └── Extracts requirements (freq, bw, family, materials)
       └── Updates DesignPanel form values

4. OPTIMIZE REQUEST
   User clicks "Start Pipeline" (or auto-triggered)
   └── OptimizeWorker
       ├── RequestBuilder.build_optimize_request()
       ├── material_resolver.resolve_materials()  ← stamp materials
       └── POST /api/v1/optimize
           └── ResponseHandler.parse_optimize_response()
               └── If status=="accepted" + command_package → trigger execution

5. CST EXECUTION
   ExecutionWorker
   ├── CommandParser.parse_package(command_package)
   │   └── V2CommandContractValidator.validate_package()  ← if v2
   └── ExecutionEngine.execute_command_package(package)
       ├── CSTApp.connect()  ← attach to CST or dry_run
       └── for each Command:
           ├── VBAGenerator.generate(command)
           │   ├── Load template from templates/*.vba
           │   └── Substitute params
           ├── CSTApp.execute_macro(vba)
           │   ├── mws.add_to_history(title, vba)
           │   └── mws.full_history_rebuild()
           └── Record ExecutionResult

6. RESULT FEEDBACK
   FeedbackWorker
   ├── CSTApp.export_s_parameters(path)
   ├── ResultExtractor.extract_metrics(s11_file)
   ├── SessionStore.update_session(metrics)
   └── POST /api/v1/result {session_id, metrics, artifacts}

7. ITERATION / CONVERGENCE
   Server decides:
   ├── Converged → pipeline done, show final design
   └── Not converged → returns new command_package → back to step 5

8. EXPORT (optional)
   ExportWorker
   └── DesignExporter.export_to_json/csv(design, path)
```

---

## 8. Configuration

**File:** `config.json`

```json
{
  "server": {
    "base_url": "http://192.168.234.112:8000",
    "timeout_sec": 60,
    "retry_count": 3,
    "retry_backoff": 2
  },
  "cst": {
    "executable_path": "C:\\Program Files (x86)\\CST Studio Suite 2024\\CST DESIGN ENVIRONMENT.exe",
    "project_dir": "E:\\antenna\\app",
    "default_units": "mm",
    "frequency_units": "ghz",
    "auto_save": true,
    "save_interval_sec": 300
  },
  "ui": {
    "theme": "light",
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

The `client_capabilities` block is sent verbatim in every `OptimizeRequest` so the server knows what the client can handle.

---

## 9. Data Models

### OptimizeRequest (sent to server)
```json
{
  "schema_version": "optimize_request.v1",
  "user_request": "design a 2.4 GHz AMC patch with FR-4 substrate",
  "target_spec": {
    "frequency_ghz": 2.4,
    "bandwidth_mhz": 100.0,
    "antenna_family": "amc_patch",
    "patch_shape": "auto",
    "feed_type": "auto"
  },
  "design_constraints": {
    "substrate_materials": ["Rogers RO3003"],
    "conductor_materials": ["Copper (annealed)"],
    "max_size_mm": null
  },
  "optimization_policy": { "max_iterations": 5, "convergence_threshold": 0.01 },
  "runtime_preferences": { "simulation_timeout_sec": 600 },
  "client_capabilities": { "supports_farfield_export": true, ... },
  "session_id": "abc-123"
}
```

### OptimizeResponse (received from server)
```json
{
  "schema_version": "optimize_response.v1",
  "status": "accepted",
  "session_id": "abc-123",
  "trace_id": "tr-456",
  "ann_prediction": {
    "ann_model_version": "v2.1",
    "confidence": 0.92,
    "dimensions": {
      "patch_length_mm": 29.5,
      "patch_width_mm": 38.0,
      "substrate_height_mm": 1.6
    }
  },
  "command_package": {
    "schema_version": "cst_command_package.v2",
    "session_id": "abc-123",
    "commands": [...]
  }
}
```

### Command (inside command_package)
```json
{
  "seq": 3,
  "command": "define_material",
  "params": {
    "name": "Rogers RO3003",
    "epsilon_r": 3.0,
    "loss_tangent": 0.0013,
    "mu_r": 1.0
  },
  "on_failure": "abort"
}
```

---

## 10. Design Decisions & Patterns

| Decision | Rationale |
|----------|-----------|
| **QThread + asyncio** | Qt event loop can't block; worker threads create separate asyncio event loops for each HTTP request batch. |
| **Pydantic models at schema boundaries** | Both `OptimizeRequest` / `OptimizeResponse` / `CommandPackage` are Pydantic-validated — errors caught before reaching CST. |
| **Dry-run mode** | CST is only available on Windows with the suite installed. Dry-run lets the entire pipeline run and be tested without CST present. |
| **VBA template files** | Separating VBA logic from Python makes the templates readable, diffable, and editable by CST engineers without Python knowledge. |
| **Single material resolver** | All three entry points (form values, server response, command package) feed into one `resolve_materials()` — eliminates divergent material name handling bugs. |
| **Session persistence to disk** | Sessions survive app restarts; enables recovery from crashes mid-iteration. |
| **V2 command contract JSON** | The strict v2 schema is a config file, not hard-coded, enabling the server to evolve the command set without client code changes. |
| **WebSocket for live events** | Polling `/api/v1/sessions/{id}` would hammer the server; WebSocket push delivers iteration events with zero latency. |
