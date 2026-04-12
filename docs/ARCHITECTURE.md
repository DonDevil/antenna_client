# Architecture

This document describes the complete file structure, purpose of every module, every third-party library used, and the full end-to-end workflow of the Antenna Optimization Client.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Repository Layout](#repository-layout)
3. [Source Modules (`src/`)](#source-modules-src)
   - [comm — Server Communication Layer](#comm--server-communication-layer)
   - [executor — Command Execution Layer](#executor--command-execution-layer)
   - [cst_client — CST Studio Interface](#cst_client--cst-studio-interface)
   - [session — Session & Persistence Layer](#session--session--persistence-layer)
   - [ui — Desktop UI Layer](#ui--desktop-ui-layer)
   - [utils — Shared Utilities](#utils--shared-utilities)
   - [tools — Offline Antenna Calculators](#tools--offline-antenna-calculators)
4. [Scripts](#scripts)
5. [Tests](#tests)
6. [Configuration & Schema](#configuration--schema)
7. [Artifacts & Outputs](#artifacts--outputs)
8. [Libraries & Dependencies](#libraries--dependencies)
9. [End-to-End Workflow](#end-to-end-workflow)
10. [Server API Contract](#server-api-contract)
11. [CST Studio Integration](#cst-studio-integration)
12. [VBA Template Catalog](#vba-template-catalog)
13. [Session Lifecycle](#session-lifecycle)
14. [Offline / Dry-Run Mode](#offline--dry-run-mode)

---

## System Overview

The Antenna Optimization Client is a **Windows desktop application** written in Python that serves as the front-end to a remote antenna optimization server. Its responsibilities are:

1. **Gather user intent** — through a conversational chat UI or direct design panel inputs.
2. **Send optimization requests** — to the remote server (`antenna_server`) over HTTP REST.
3. **Receive a command package** — a structured list of CST Studio commands returned by the server (produced by the server's ANN model / LLM reasoning pipeline).
4. **Execute commands in CST Studio** — by generating VBA macros and injecting them into the live CST Design Environment through its COM/Python API.
5. **Extract simulation results** — S-parameters, far-field metrics, and export artifacts from CST.
6. **Post results back to the server** — so the server can refine its model or confirm convergence.
7. **Persist sessions and checkpoints** — to disk for crash recovery, audit trails, and offline export.

The server is accessed at a configurable base URL (default `http://10.150.60.38:8000`). The client never performs electromagnetic simulation itself — all antenna physics and dimension prediction are done server-side. The client is purely responsible for orchestrating CST Studio and managing the feedback loop.

---

## Repository Layout

```
antenna_client/
├── main.py                     # Root entry point (thin wrapper → src/main.py)
├── config.json                 # Application configuration (server URL, CST path, UI, logging)
├── requirements.txt            # Python package dependencies
├── pyrightconfig.json          # Pyright type checker configuration
│
├── src/                        # All application source code
│   ├── main.py                 # Application launcher (starts PySide6 QApplication)
│   ├── comm/                   # HTTP/WebSocket server communication layer
│   ├── executor/               # Command parsing, VBA generation, execution engine
│   ├── cst_client/             # CST Studio automation (COM API wrapper)
│   ├── session/                # Session management, checkpoints, persistence
│   ├── ui/                     # PySide6 desktop UI widgets
│   ├── utils/                  # Logging, validation, constants, health checks
│   └── tools/                  # Offline antenna parameter calculators
│
├── scripts/                    # Standalone CLI scripts for testing and automation
├── tests/                      # Unit and integration test suite
├── config/schema/              # JSON schema contracts for server command packages
├── artifacts/                  # Runtime output directory (exports, reports, VBA, .cst files)
├── logs/                       # Rotating application logs
├── docs/                       # Documentation
└── data/raw/                   # Reserved for raw training/measurement data
```

---

## Source Modules (`src/`)

### Entry Points

#### `main.py` (root)
Thin repository entry point that inserts `src/` and the project root into `sys.path`, then delegates to `src/main.py`. Exists so that `python main.py` works from the repository root without manual path setup.

#### `src/main.py`
True application launcher. Creates a `QApplication`, instantiates `MainWindow`, calls `window.show()`, and enters the Qt event loop. Also sets the application name and version from `utils.constants`.

---

### `comm/` — Server Communication Layer

All HTTP and WebSocket communication with the remote `antenna_server` lives here. No antenna physics is performed in this layer.

#### `comm/server_connector.py` — `ServerConnector`
Low-level async HTTP client built on top of `httpx.AsyncClient`. Responsibilities:
- Opens a connection pool to the configured `base_url` (max 10 connections, 5 keepalive).
- Implements `GET` and `POST` methods with **exponential backoff retry** (configurable retry count and backoff multiplier from `config.json`).
- Must be used as an async context manager (`async with ServerConnector(...) as connector`).
- Sets a configurable timeout per request (default 60 s).

#### `comm/api_client.py` — `ApiClient`
High-level REST wrapper that calls `ServerConnector` and delegates response parsing to `ResponseHandler`. Exposes the following server endpoints:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `optimize()` | `POST /api/v1/optimize` | Submit antenna design request; receive command package |
| `send_result()` | `POST /api/v1/result` | Post CST simulation results back to server |
| `send_feedback()` | alias for `send_result()` | Backward-compatible alias |
| `chat()` | `POST /api/v1/chat` | Conversational message exchange for intent capture |
| `parse_intent()` | `POST /api/v1/intent/parse` | Ask server to parse intent without triggering optimization |
| `get_session()` | `GET /api/v1/sessions/{id}` | Fetch live session state from server |
| `load_capabilities()` | `GET /api/v1/capabilities` | Retrieve server capability catalog |

#### `comm/request_builder.py` — `RequestBuilder`, `OptimizeRequest`
Constructs the JSON payload sent to `/api/v1/optimize`. The payload schema is enforced by the `OptimizeRequest` Pydantic model. Key fields assembled:

- `schema_version` — protocol version string.
- `user_request` — raw natural-language text from the user.
- `target_spec` — antenna family, frequency, bandwidth, shape, feed type, polarization, gain/efficiency/VSWR targets.
- `design_constraints` — substrate and conductor material selections resolved through `material_resolver`.
- `optimization_policy` — iteration budget, convergence threshold, exploration strategy.
- `runtime_preferences` — priority (`"normal"`), simulation timeout.
- `client_capabilities` — declares what the client can export (far-field, S-params, formats).
- `session_id` — present on subsequent iterations to continue an existing server session.

Contains per-family substrate defaults (`FAMILY_DEFAULT_SUBSTRATES`) and target defaults (`FAMILY_DEFAULT_TARGETS`) for the three supported antenna families: `microstrip_patch`, `amc_patch`, `wban_patch`.

#### `comm/response_handler.py` — `ResponseHandler`, `OptimizeResponse`, `AnnPrediction`
Parses the raw JSON dict returned by `/api/v1/optimize` into a validated `OptimizeResponse` Pydantic model. Key response fields:

- `status` — `"accepted"`, `"completed"`, `"clarification_required"`, or `"error"`.
- `session_id`, `trace_id` — identifiers for correlating requests and server logs.
- `ann_prediction` — server's ANN model dimension predictions (patch/substrate/feed dimensions in mm, confidence score).
- `command_package` — the structured list of CST commands to execute (dict, parsed further by `executor.command_parser`).
- `clarification` — present when the server needs more information before it can generate commands.
- `warnings` — non-fatal notices from the server.
- `error` — present when `status == "error"`; contains error code and message.

`handle_optimize_response()` maps the status to an action dict (`execute`, `clarify`, `error`).

#### `comm/error_handler.py` — `ErrorHandler`, `ErrorCode`, `ErrorRecovery`
Defines all server error codes (per the server handoff spec section 10) as an `ErrorCode` enum:

| Code | Meaning |
|------|---------|
| `SCHEMA_VALIDATION_FAILED` | Request JSON failed server schema validation (HTTP 422) |
| `FAMILY_NOT_SUPPORTED` | Requested antenna family not in server catalog |
| `FAMILY_PROFILE_CONSTRAINT_FAILED` | Frequency/bandwidth outside family profile |
| `INVALID_INTENT_REQUEST` | Intent parse endpoint rejected the request |
| `INVALID_CHAT_REQUEST` | Chat endpoint rejected the message |
| `V2_COMMAND_VALIDATION_FAILED` | Server rejected its own command package |
| `SESSION_NOT_FOUND` | Session expired or never existed |
| `FEEDBACK_PROCESSING_FAILED` | Server could not process result submission |
| `LOW_SURROGATE_CONFIDENCE` | Server's surrogate model has low confidence in predictions |

Maps each code to a user-friendly message, a recoverability flag, and a suggested recovery action string.

#### `comm/ws_client.py` — `SessionEventListener`
WebSocket client for **real-time streaming** of server-side session events. Connects to `ws://<host>/api/v1/sessions/{session_id}/stream`. Supports:
- Event-type dispatch (`on_event("iteration.completed", handler)`).
- Error handlers (`on_error(handler)`).
- Clean disconnect and reconnect logic.
- Runs in its own async task via `listen()`.

Used to receive live progress updates during long-running server-side optimizations without polling.

#### `comm/initializer.py` — `ClientInitializer`, `InitializationState`
Manages the **startup handshake sequence** between client and server:
1. `GET /api/v1/health` — verify server is alive and read ANN/LLM status.
2. Poll health until `ann_status` and `llm_status` are ready (if server is still loading).
3. `GET /api/v1/capabilities` — load the server's capability catalog.
4. Build `InitializationState` that the UI reads to decide what is enabled.

Progress callbacks are fired at each step, allowing the UI `InitializationWorker` thread to relay messages to the status bar.

#### `comm/intent_parser.py` — `IntentParser`
**Local (offline) NLP fallback** used when the server is unavailable. Extracts:
- Action (`design`, `optimize`, `analyze`, `compare`) via keyword matching.
- Antenna type from a registered list of known antenna names.
- Frequency in GHz (regex patterns for `2.4 GHz`, `2400 MHz`, etc.).
- Bandwidth in MHz.
- Physical constraints (size, compact, etc.).
- Confidence score based on how many fields were found.

Not used in the live server path; activates only in offline / degraded-connection scenarios.

#### `comm/antenna_commands.py` — `AntennaFamily`, `RectPatchCommand`, `AMCPatchCommand`, `WBANPatchCommand`
Pydantic models that define the **client-side command structures** for each antenna family. These are used when building the `target_spec` section of the optimize request. Key constraints are encoded as Pydantic `Field` validators (min/max frequency, bandwidth, gain, efficiency, VSWR, AMC array size). The server uses these as authoritative constraints when selecting dimensions.

---

### `executor/` — Command Execution Layer

Translates the server's high-level command package into actual CST Studio operations: parameter mutations, geometry creation, solver invocation, and result export.

#### `executor/command_parser.py` — `CommandParser`, `CommandPackage`, `Command`
Parses and validates the raw `command_package` dict from the server into a structured `CommandPackage` Pydantic model. Key fields:

- `schema_version` — `"cst_command_package.v1"` or `"cst_command_package.v2"`.
- `session_id`, `trace_id`, `design_id`, `iteration_index`.
- `units` — geometry and frequency unit declarations.
- `predicted_dimensions` — ANN-predicted dimension values.
- `commands` — ordered list of `Command` objects, each with `seq`, `command` (type), `params`, `on_failure`, `checksum_scope`.
- `expected_exports` — list of artifact types the server expects to receive back.
- `safety_checks` — list of pre-execution guards.

`CommandParser` validates the schema version, normalizes legacy field aliases (`type` → `command`, `parameters` → `params`), and optionally runs V2 contract validation via `V2CommandContractValidator`.

#### `executor/v2_command_contract.py` — `V2CommandContractValidator`
Loads `config/schema/cst_command_package.v2.command_contract.json` and validates each command's parameters against the contract. Enforces:
- Required parameters for every command type.
- Geometry commands must have a `component` field.
- Parameter mutation commands must have `name` and `expression`.
- Export/simulation commands are always allowed.

This catches server-generated command packages that violate the agreed API contract before any CST calls are attempted.

#### `executor/vba_generator.py` — `VBAGenerator`
Translates individual `Command` objects into **CST VBA macro strings**. For each recognized command type it emits the corresponding VBA Object statements. Includes full material preset macros for common materials (Gold, Copper, Silver, Aluminum, FR-4, Rogers substrates) with all required CST property fields. Key command types handled:
- `define_material` — emits `Material` VBA block with epsilon, conductivity, loss tangent.
- `create_substrate` / `create_ground_plane` / `create_patch` / `create_feedline` — emits `Brick` geometry VBA.
- `define_parameter` / `update_parameter` — emits `StoreParameter` VBA.
- `create_port` — emits `Port` VBA with impedance and position.
- `set_frequency_range` — emits frequency solver settings.
- `set_units` — emits unit setup block.
- `run_simulation` — emits `Solver.Start`.
- `export_s_parameters` / `extract_summary_metrics` / `export_farfield` — emits export VBA.
- Boolean operations (`boolean_add`, `boolean_subtract`, etc.) — emits solid assembly VBA.

Also loads pre-authored `.vba` template files from `executor/templates/` when available, filling in parameter placeholders.

#### `executor/execution_engine.py` — `ExecutionEngine`, `ExecutionResult`
The main orchestrator. For a given `CommandPackage`:
1. Connects to CST Studio (`CSTApp.connect()`).
2. If CST is unavailable, enters **dry-run mode** (logs what would be executed, does not call CST).
3. Iterates through the ordered command list.
4. For each command: generates VBA via `VBAGenerator`, calls `CSTApp.run_history_macro()` to inject and execute, captures result.
5. Maintains a **geometry context** (what shapes have been created), **parameter context** (current parameter values), and **material context** (defined materials) to provide scoped hints to the VBA generator.
6. Supports **pause/resume** — checks a `paused` flag between commands and yields control.
7. Collects `ExecutionResult` objects (`command_id`, `success`, `output`, `error`, `macro`).
8. Tracks artifact paths for everything exported during execution.

#### `executor/progress_tracker.py` — `ProgressTracker`
Tracks per-command execution progress: total commands, completed, failed, start/end time, per-command timestamps, and ETA. Provides percentage completion and estimated time remaining derived from average command duration.

#### `executor/templates/` — VBA Template Files
31 pre-authored `.vba` files, one per recognized command type. Each file is a VBA snippet with named placeholder fields that `VBAGenerator` fills in at runtime. Examples:
- `cmd_create_patch.vba`, `cmd_create_substrate.vba`, `cmd_create_feedline.vba` — geometry construction.
- `cmd_define_material.vba` — material definition block.
- `cmd_run_solver.vba` — solver start command.
- `cmd_export_s11.vba` — S-parameter file export.
- `cmd_define_brick.vba`, `cmd_define_sphere.vba`, `cmd_define_cone.vba`, etc. — primitive shapes.
- `cmd_boolean_subtract.vba`, `cmd_boolean_add.vba` — solid Boolean operations.
- `cmd_pick_face.vba`, `cmd_pick_edge.vba`, `cmd_pick_endpoint.vba` — geometry selection.

---

### `cst_client/` — CST Studio Interface

Wraps the official CST Python automation API (installed with CST Studio Suite 2024). All COM/Python API calls are isolated here so the rest of the codebase remains CST-agnostic.

#### `cst_client/cst_app.py` — `CSTApp`
The primary CST interface. Responsibilities:
- `connect()` — attach to a running CST Design Environment instance (via `import cst; cst.interface.DesignEnvironment()`). If no instance is running it attempts to launch the executable from `config.json` → `cst.executable_path`. Returns `False` on non-Windows platforms.
- `_refresh_active_project()` — syncs the `project` and `mws` (model 3D) handles after CST operations that may switch the active project.
- `run_history_macro(title, vba_code)` — calls `mws.add_to_history(title, vba_code)` followed by `mws.full_history_rebuild()` to execute VBA without raising the CST macro editor.
- `_resolve_artifact_path(hint, extension)` — resolves output paths under `artifacts/exports/`.
- `is_connected()` — returns current connection state.
- Loads project directory and CST executable path from `config.json`.

#### `cst_client/vba_executor.py` — `VBAExecutor`
Helper class for injecting and running VBA macros through an existing `CSTApp`. Provides:
- `execute_macro(vba_code)` — calls `add_to_history` / `full_history_rebuild`.
- `execute_vb_statement(statement)` — evaluates a single VB expression and returns the result.
- `define_material(name, epsilon_r, loss_tangent)` — convenience wrapper for material creation.

#### `cst_client/project_manager.py` — `ProjectManager`
Manages CST project lifecycle:
- `create_project(name)` — creates a new `.cst` file.
- `open_project(path)` — opens an existing project.
- `save_project()` / `save_project_as(path)` — saves current state.
- `close_project()` — closes without saving.
- Auto-creates the project directory on initialization.

#### `cst_client/result_extractor.py` — `ResultExtractor`
Reads simulation output files (S-parameter CSVs/TXTs exported by VBA) and extracts structured metrics:
- `extract_s11(result_file)` — parses frequency vs. S11 (dB) columns.
- `extract_metrics(s11_data)` — derives center frequency, bandwidth, return loss, VSWR, gain.
- `find_center_frequency(frequencies, s11_db)` — finds the minimum S11 point.
- `find_bandwidth(frequencies, s11_db, threshold_db)` — finds the -10 dB bandwidth.

---

### `session/` — Session & Persistence Layer

Maintains the state of a design workflow across multiple server round-trips and across application restarts.

#### `session/session_store.py` — `SessionStore`, `Session`
In-memory `dict` of `Session` objects, with **JSON file persistence** to `test_checkpoints/` (root level). Each `Session` tracks:
- `session_id`, `trace_id`, `design_id` — server-assigned identifiers.
- `user_request` — original user text.
- `status` — `active`, `completed`, `failed`, `paused`.
- `current_iteration` — iteration counter.
- `command_package` — last received command package.
- `results` — list of per-iteration result dicts.
- `metadata` — extension dict for arbitrary session data.

Sessions are serialized to `{session_id}.json` on update and loaded back on startup for recovery.

#### `session/checkpoint_manager.py` — `CheckpointManager`
Saves and restores execution checkpoints to `checkpoints/` directory. Each checkpoint is a JSON snapshot of the execution state at a moment in time, keyed by `session_id`. Used for crash recovery: if CST crashes mid-execution, the client can reload the last checkpoint and resume from the last successful command.

#### `session/design_store.py` — `DesignStore`, `Design`
In-memory store for `Design` objects (distinct from sessions). A design tracks:
- `design_id`, `specifications`, `status` (`draft`, `active`, `completed`, `archived`).
- `iterations` — history of iteration parameter/results pairs.
- `metadata` — extensible dict.

#### `session/iteration_tracker.py` — `IterationTracker`
Records per-iteration metadata (`session_id`, `iteration_num`, `design_params`, `results`). Provides:
- `detect_convergence(session_id, threshold)` — checks if center frequency changed by less than `threshold` between the last two iterations (default 1%).
- `compare_iterations(session_id, iter1, iter2)` — returns a diff dict highlighting metric changes.

#### `session/design_exporter.py` — `DesignExporter`
Exports design data to files:
- `export_to_json(design_dict, filepath)` — writes a pretty-printed JSON file.
- `export_to_csv(designs, filepath)` — writes a multi-row CSV from a list of design dicts.
- Used for saving final design parameters and iteration histories as reports.

#### `session/error_recovery.py` — `ErrorRecovery`
Tracks error counts and recovery attempts. Handles:
- `handle_network_error(error)` — allows up to 3 retry events before failing permanently.
- `handle_cst_crash()` — sets a recovery flag and attempts a CST restart.
- `get_recovery_status()` — returns current error/recovery state dict.

#### `session/config_manager.py` — `ConfigManager`
Loads and provides `config.json` values with dot-notation key access (`get("server.base_url")`). Falls back to built-in defaults if the file is missing or malformed.

#### `session/chat_history.py` — `ChatHistory`
Per-session message store. Stores `{"sender", "text", "timestamp"}` dicts. Supports `add_message()`, `get_messages(limit)`, `clear()`, and `export_to_dict()`. Used by the UI to persist and replay conversation history across reconnections.

---

### `ui/` — Desktop UI Layer

PySide6 (Qt 6) widgets organized around a split-panel layout.

#### `ui/main_window.py` — `MainWindow`
The top-level `QMainWindow`. Layout:
- Horizontal `QSplitter` containing `DesignPanel` (left) and `ChatWidget` (right).
- `AppStatusBar` at the bottom.
- Menu bar with File, View, Help actions.

On startup, runs `InitializationWorker` (a `QThread`) which performs the health + capabilities check in a background event loop and emits progress signals to the status bar. Also manages a `HealthMonitorWorker` for periodic 30-second health polling. Connects `DesignPanel` signals to `ChatMessageHandler` actions.

**Worker threads** defined here (all subclass `QThread`):
- `ConnectionWorker` — one-shot health check.
- `InitializationWorker` — runs `ClientInitializer.initialize()` asynchronously.

#### `ui/chat_widget.py` — `ChatWidget`
The conversational chat interface. Features:
- `QTextEdit` read-only display with styled user/assistant message formatting.
- `QTextEdit` input field with Shift+Enter for newlines, Enter to send.
- `Send` button.
- `message_submitted` signal emitted to the main window on send.
- `add_message(sender, text)` — appends a formatted message block to the display.
- Auto-scrolls to the latest message.

#### `ui/design_panel.py` — `DesignPanel`
Left-side form panel for direct antenna parameter entry. Controls:
- `QComboBox` for antenna family (`microstrip_patch`, `amc_patch`, `wban_patch`).
- `QDoubleSpinBox` for frequency (GHz) and bandwidth (MHz).
- `QComboBox` for conductor and substrate material selection.
- `QComboBox` for patch shape, feed type, polarization.
- Buttons: **Start Pipeline**, **Reset**, **Export**, **Send Feedback**.
- Emits `design_changed(dict)`, `start_pipeline_requested()`, `reset_requested()`, `export_requested()`, `feedback_requested(dict)` signals.
- Contains `FAMILY_MATERIAL_DEFAULTS` and `FAMILY_QUALIFIER_DEFAULTS` dicts to auto-populate sensible defaults when the family changes.

#### `ui/status_bar.py` — `AppStatusBar`
Custom `QStatusBar` with:
- Server connection label (Connected / Disconnected).
- CST availability label (Available / Not Available).
- `QProgressBar` (hidden when idle, shown during execution).
- `showMessage()` with configurable timeout.

#### `ui/styles.qss` — Qt StyleSheet
Application-wide Qt stylesheet. Defines the color palette, fonts, borders, and hover states for all widgets. Provides a clean flat-design look using Segoe UI on Windows.

---

### `utils/` — Shared Utilities

Cross-cutting concerns used by every other module.

#### `utils/logger.py` — `get_logger()`, `SafeConsoleHandler`
Configures Python's `logging` module. Each module calls `get_logger(__name__)` to get its own named logger. Configuration:
- Level: `INFO` (configurable).
- Handlers: `SafeConsoleHandler` (console) + `RotatingFileHandler` (file).
- Log file: `logs/antenna_client.log`, max 10 MB, 5 backups.
- `SafeConsoleHandler` catches `UnicodeEncodeError` on Windows legacy console encodings and re-encodes with `errors="replace"` to prevent crashes on emoji/special characters.

#### `utils/constants.py`
Application-wide string and numeric constants: `APP_NAME`, `APP_VERSION`, default server URL, default CST paths, default window dimensions, log levels.

#### `utils/validators.py` — `DesignSpecification`, `CommandPackage`, helpers
Pydantic models for validating user-facing design inputs. Provides `validate_design_spec()` and `validate_command_package()` helpers. Also exports `extract_antenna_family(text)` and `extract_frequency_bandwidth(text)` regex-based extractors used by `RequestBuilder` to parse natural-language inputs into structured fields. Contains `FAMILY_ALIASES` mapping colloquial names (`"patch"`, `"amc"`) to canonical server family IDs.

#### `utils/material_resolver.py` — `resolve_materials()`, `MaterialChoice`, `normalize_material_name()`
**Single authoritative material resolution point** for the entire pipeline. Every module that needs to pick conductor/substrate materials delegates here instead of maintaining its own fallback chain. Provides:
- `FAMILY_DEFAULT_SUBSTRATES` — per-family substrate defaults that match server expectations.
- `FALLBACK_CONDUCTOR` (`"Copper (annealed)"`) and `FALLBACK_SUBSTRATE` (`"FR-4 (lossy)"`).
- `resolve_materials(family, design_specs, capabilities)` — combines family defaults with user overrides and server capability allowlists into a `MaterialChoice` dataclass.
- `normalize_material_name(raw)` — canonical form (underscores → spaces, collapsed whitespace).
- `stamp_materials_on_package(package, materials)` — injects resolved material names into a command package dict so all commands reference the same material strings.

#### `utils/connection_checker.py` — `ConnectionChecker`
Static class providing async health probes:
- `check_server()` — sends `GET /api/v1/health`, parses the response, returns `(is_connected, status_message, health_dict)`. Reports ANN and LLM subsystem status strings from the health payload.
- `check_cst()` — verifies that the CST executable path exists on disk.
- `check_all()` — runs both checks and returns a combined `{"server": ..., "cst": ...}` result dict.

#### `utils/health_monitor.py` — `HealthMonitor`, `HealthMonitorWorker`
Runs `ConnectionChecker.check_all()` on a background `QThread` every 30 seconds (configurable). Emits `health_updated(dict)` signal when results arrive. `HealthMonitor` wires the worker signals to `AppStatusBar` updates. Shuts down cleanly on application exit using a `running` flag and 100 ms sleep slices.

#### `utils/chat_message_handler.py` — `ChatMessageHandler`, `_BaseWorker` and worker classes
The **central UI workflow controller** — the "glue" layer that connects all modules together in response to user actions. Contains multiple inner `QThread` worker classes:

- `ChatRequestWorker` — sends a chat message to `POST /api/v1/chat`, receives assistant reply, emits `response_ready(dict)`.
- `OptimizeWorker` — builds an optimize request via `RequestBuilder`, sends it via `ApiClient`, parses the response, and emits the `CommandPackage` for execution.
- `ExecutionWorker` — runs `ExecutionEngine.execute_command_package()` in a thread, emits per-command progress and final result list.
- `FeedbackWorker` — posts extracted CST metrics to `POST /api/v1/result`.
- `ExportWorker` — calls `DesignExporter` to save design data to JSON/CSV.

Each worker subclasses `_BaseWorker` which provides `_load_base_url()` (reads `config.json`) and `_run_async(coro)` (creates a fresh event loop and runs the coroutine to completion).

---

### `tools/` — Offline Antenna Calculators

Standalone calculators for **local dimension estimation** without server contact. Used for sanity-checking, offline mode, and script-based training data generation.

#### `tools/antenna_calculations/rect_patch_calculator.py` — `RectangularPatchCalculator`
Implements closed-form equations for rectangular microstrip patch antennas:
- `calculate_dimensions(freq_ghz, substrate)` — effective permittivity, patch width/length using the transmission-line model, feed width for 50 Ω, inset feed offset.
- `predict_performance(dims, substrate, freq_ghz)` — bandwidth (Q-factor method), return loss, VSWR, gain (3–7 dBi estimated), radiation efficiency.

Uses `SubstrateProperties`, `RectPatchDimensions`, `RectPatchPerformance` dataclasses.

#### `tools/antenna_calculations/amc_calculator.py` — `AMCCalculator`
Calculates AMC (Artificial Magnetic Conductor) unit cell and array parameters:
- `calculate_unit_cell(freq_ghz, substrate, rows, cols)` — period, patch size, gap dimensions for the unit cells.
- `predict_performance(dims, patch_freq_ghz)` — reflection phase at resonance, phase bandwidth, gain improvement (+2–3 dB), back-lobe reduction.
- `is_matched_to_patch(amc_freq, patch_freq, tolerance_pct)` — validates that AMC resonance is within ±2–3% of the patch frequency (critical constraint).

#### `tools/antenna_calculations/wban_calculator.py` — `WBANCalculator`
WBAN (Wearable Body Area Network) antenna calculator:
- `calculate_dimensions(freq_ghz, substrate, body_props)` — applies frequency upshift compensation (3–10%) to account for body loading, ground slot dimensions.
- `predict_performance(dims, substrate, body_props, freq_ghz)` — predicts free-space and on-body gain/efficiency, frequency shift when worn, SAR (1 g and 10 g averages).
- `is_safe(performance)` — checks SAR against regulatory limits (1.6 W/kg for 1 g, 2.0 W/kg for 10 g).

Uses `BodyProperties`, `WBANDesignParameters`, `WBANPerformance` dataclasses.

#### `tools/prepare_offline_feedback.py`
CLI script that builds a complete result payload for `POST /api/v1/result` from locally available artifacts, without CST running. It:
1. Scans `artifacts/exports/` for the latest `*_metrics.json` file containing far-field data.
2. Extracts the most recent `session_id`, `trace_id`, `design_id` from `logs/antenna_client.log` via regex.
3. Constructs a properly formatted result payload.
4. Writes it to `artifacts/exports/offline_feedback.json` for manual inspection or replay.

---

## Scripts

Standalone CLI scripts under `scripts/`. All add the project root and `src/` to `sys.path` before importing from `src/`.

| File | Purpose |
|------|---------|
| `health_check.py` | Connects to `GET /api/v1/health` and prints server/ANN/LLM status |
| `run_cst_pipeline_once.py` | End-to-end test: optimize → CST execute → result post (rectangular patch) |
| `run_amc_pipeline_once.py` | End-to-end test: optimize → CST execute → result post (AMC patch, up to 5 iterations) |
| `workflow_validation.py` | Validates the complete server handshake sequence without a real CST instance |
| `diagnose_server.py` | Detailed server diagnostics: health, capabilities, schema version inspection |
| `verify_request.py` | Builds a sample optimize request and pretty-prints it for payload inspection |
| `schema_comparison.py` | Compares local V2 command contract schema against live server capabilities |
| `debug_schema_validation.py` | Sends deliberately invalid payloads to verify server-side validation responses |
| `generate_rect_patch_feedback.py` | Generates synthetic feedback payloads for rectangular patch designs |
| `autotrain.py` | Automation script for training data collection loops |
| `check_rect_patch_ann_route.py` | Verifies that the server routes rectangular patch requests to the ANN model |
| `test_amc_server_params_vs_client.py` | Cross-checks AMC command parameters between server response and client contract |
| `test_cst_parameter_workflow.py` | Tests the parameter update/rebuild workflow in CST |
| `run_integration_tests.py` | Runs the integration test suite |
| `run_real_integration_tests.py` | Runs integration tests with a real CST instance |

---

## Tests

Under `tests/`. Split into unit tests and integration tests.

### `tests/unit/`

| File | Tests |
|------|-------|
| `test_antenna_calculators.py` | `RectangularPatchCalculator`, `AMCCalculator`, `WBANCalculator` local math |
| `test_antenna_commands.py` | `AntennaFamily`, `RectPatchCommand`, `AMCPatchCommand`, `WBANPatchCommand` Pydantic models |
| `test_api_client.py` | `ApiClient` endpoint calls (mocked HTTP) |
| `test_chat_routing_rules.py` | Chat intent routing and mode selection |
| `test_chat_validation.py` | Chat request payload validation |
| `test_command_parser.py` | `CommandParser` schema version handling and field normalization |
| `test_cst_command_console.py` | VBA console simulation |
| `test_cst_execution_extraction.py` | Result extraction from simulated CST output |
| `test_cst_farfield_fallback.py` | Far-field export fallback path |
| `test_execution_artifact_scoping.py` | Artifact path scoping in `ExecutionEngine` |
| `test_farfield_monitor_vba.py` | `add_farfield_monitor` VBA generation |
| `test_implement_amc_command.py` | Full `implement_amc` command execution path |
| `test_material_resolver.py` | `material_resolver` resolution priority and fallback |
| `test_material_selection_flow.py` | Material selection in `DesignPanel` / `RequestBuilder` |
| `test_qml_cst_results_view.py` | Result rendering in UI |
| `test_qml_done_flow.py` | Completion flow through UI |
| `test_request_builder.py` | `RequestBuilder.build_optimize_request()` payload shape |
| `test_v2_execution_smoke.py` | Smoke test for V2 command package execution |
| `test_vba_generator.py` | `VBAGenerator` output for all command types |
| `test_vba_generator_v2.py` | `VBAGenerator` V2 command contract compliance |
| `test_workflow_simple.py` | Simplified end-to-end workflow mock |

### `tests/integration/`

| File | Tests |
|------|-------|
| `test_full_pipeline.py` | Full optimize → execute → feedback loop with mocked server |
| `test_integration_suite.py` | Multi-step integration scenarios |

### `tests/calculators/`, `tests/fixtures/`
Supporting test data and fixtures used by the unit and integration tests.

---

## Configuration & Schema

### `config.json`
Root-level application configuration:

```json
{
  "server": {
    "base_url": "http://10.150.60.38:8000",   // Target antenna_server address
    "timeout_sec": 60,                          // Per-request HTTP timeout
    "retry_count": 3,                            // Retry attempts on failure
    "retry_backoff": 2                           // Exponential backoff multiplier
  },
  "cst": {
    "executable_path": "...",                   // CST Studio Suite 2024 executable
    "project_dir": "E:\\antenna\\app",           // Base directory for CST projects
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

### `config/schema/cst_command_package.v2.command_contract.json`
JSON schema contract that defines required parameters for each V2 command type. Loaded by `V2CommandContractValidator` at startup. Commands covered: `create_project`, `set_units`, `set_frequency_range`, `define_material`, `create_substrate`, `create_ground_plane`, `create_patch`, `create_feedline`, `create_port`, `set_boundary`, `set_solver`, `add_farfield_monitor`, `run_simulation`, `export_s_parameters`, `extract_summary_metrics`, `export_farfield`, `create_component`, `implement_amc`, and all geometry primitives.

---

## Artifacts & Outputs

```
artifacts/
├── exports/                    # CST simulation exports
│   ├── *_s11.csv               # S-parameter data files
│   ├── *_metrics.json          # Extracted performance metrics
│   ├── *_farfield.txt          # Far-field pattern data
│   └── offline_feedback.json   # Offline-prepared result payload
├── reports/                    # Human-readable iteration reports
├── vba/                        # Generated VBA macro files (saved for audit)
├── iface_named_project.cst     # Example CST project
└── message_test.cst            # CST project used for message protocol testing
```

`logs/`
- `antenna_client.log` — rotating log file. Contains all INFO and above messages from every module. Used by `prepare_offline_feedback.py` to extract session/trace/design IDs from log lines.

`test_checkpoints/`
- `{uuid}.json` — persisted `Session` objects from `SessionStore`.

---

## Libraries & Dependencies

All dependencies are listed in `requirements.txt`. This project targets **Python 3.10** (virtual environment in `env310/`).

| Library | Version | Purpose |
|---------|---------|---------|
| **PySide6** | 6.7.2 | Qt 6 Python bindings — the entire desktop UI. Provides `QApplication`, `QMainWindow`, `QWidget`, `QThread`, `Signal`, `QSplitter`, `QTextEdit`, `QComboBox`, `QDoubleSpinBox`, `QStatusBar`, `QProgressBar`, and all event-loop integration. |
| **httpx** | 0.27.2 | Async HTTP client with connection pooling, timeout control, and HTTP/1.1 keep-alive. Used exclusively in `ServerConnector` for all REST calls. Chosen over `requests` because it supports `async/await` natively. |
| **pydantic** | 2.11.10 | Data validation and schema enforcement. Models: `OptimizeRequest`, `OptimizeResponse`, `CommandPackage`, `Command`, `DesignSpecification`, antenna command models, ANN prediction blocks. V2 mode with `model_config` and `@model_validator`. |
| **python-dotenv** | 1.0.1 | Loads environment variables from `.env` files. Used for secrets (API keys, alternate server URLs) that should not be committed to `config.json`. |
| **pywin32** | 306 | Windows COM automation. The CST Python API returns COM objects; `pywin32` provides the underlying `win32com` dispatch layer that `cst.interface` relies on. Windows-only. |
| **pytest** | 8.3.3 | Test runner. Discovers all `test_*.py` files. Used with standard fixtures and the `conftest.py` in `tests/`. |
| **pytest-asyncio** | 0.24.0 | Pytest plugin that allows `async def test_*` test functions. Needed because `ApiClient`, `ServerConnector`, and many comm functions are async. |
| **websockets** | 13.0 | WebSocket client library. Used by `SessionEventListener` in `ws_client.py` to maintain a persistent WS connection to `ws://<server>/api/v1/sessions/{id}/stream` for real-time event streaming. |
| **aiohttp** | 3.9.5 | Async HTTP library (secondary). Present for scripts and tools that prefer `aiohttp`'s higher-level request session API. Not used in the main application path (which uses `httpx`). |

**Standard library modules used extensively:**
- `asyncio` — event loop management; worker threads create isolated event loops via `asyncio.new_event_loop()`.
- `logging` / `logging.handlers` — structured logging with rotation.
- `pathlib.Path` — all file system operations.
- `json` — config loading, checkpoint serialization, artifact writing.
- `re` — regex-based intent parsing, ID extraction from logs.
- `uuid` — session ID generation.
- `csv` — design export to CSV.
- `dataclasses` — calculator result types.
- `enum` — `AntennaFamily`, `ErrorCode`.
- `threading` — background threads in message handler.
- `platform` — Windows detection before attempting CST COM calls.

---

## End-to-End Workflow

### Phase 1 — Startup

```
python main.py
    └── src/main.py
            ├── QApplication created
            ├── MainWindow instantiated
            │       └── InitializationWorker (QThread) started
            │               ├── ServerConnector → GET /api/v1/health
            │               ├── (poll until ann_status/llm_status = ready)
            │               └── GET /api/v1/capabilities
            ├── HealthMonitor started (30 s periodic checks)
            └── window.show() → Qt event loop
```

### Phase 2 — User Provides Design Request

The user either:
- **Types in on ChatWidget** → `message_submitted` signal → `ChatMessageHandler`.
- **Fills DesignPanel form** → `start_pipeline_requested` signal → `ChatMessageHandler`.

```
ChatMessageHandler
    ├─ If chat message:
    │       ChatRequestWorker → POST /api/v1/chat
    │                               ← assistant reply text
    │                               ChatWidget.add_message("assistant", reply)
    │
    └─ If start pipeline:
            OptimizeWorker
                ├── RequestBuilder.build_optimize_request(user_text, design_specs)
                │       ├── extract_antenna_family(text)
                │       ├── extract_frequency_bandwidth(text)
                │       ├── resolve_materials(family, specs)
                │       └── → OptimizeRequest (Pydantic model)
                │
                ├── ApiClient.optimize(request.model_dump())
                │       └── ServerConnector.post("/api/v1/optimize", json=request)
                │                   ← HTTP 200 JSON response
                │
                └── ResponseHandler.parse_optimize_response(raw_json)
                        └── → OptimizeResponse (status, command_package, ann_prediction)
```

### Phase 3 — Command Execution

If `response.status == "accepted"` and `command_package` is present:

```
ExecutionWorker
    ├── CommandParser.parse_package(command_package)
    │       ├── Validate schema_version in supported versions
    │       ├── V2CommandContractValidator.validate(commands)
    │       └── → CommandPackage (session_id, trace_id, design_id, commands[])
    │
    ├── ExecutionEngine.execute_command_package(package)
    │       ├── CSTApp.connect()
    │       │       ├── import cst (CST Python API)
    │       │       ├── cst.interface.DesignEnvironment()  ← attaches to running CST
    │       │       └── self.connected = True
    │       │           (If connect() fails → dry_run = True)
    │       │
    │       └── For each Command in package.commands:
    │               ├── VBAGenerator.generate(command)
    │               │       ├── Look up template in executor/templates/
    │               │       ├── Fill parameter placeholders
    │               │       └── → vba_code (string)
    │               │
    │               ├── CSTApp.run_history_macro(title, vba_code)
    │               │       ├── mws.add_to_history(title, vba_code)
    │               │       └── mws.full_history_rebuild()
    │               │
    │               ├── ProgressTracker.command_completed(success)
    │               └── ExecutionResult(command_id, success, output, macro)
    │
    └── → List[ExecutionResult]
```

### Phase 4 — Result Extraction

After the `run_simulation` command completes:

```
CSTApp (via VBA export commands)
    ├── Export S-parameters → artifacts/exports/{hint}_s11.csv
    ├── Export far-field → artifacts/exports/{hint}_farfield.txt
    └── Extract summary metrics → artifacts/exports/{hint}_metrics.json

ResultExtractor
    ├── extract_s11(csv_path) → {frequencies, s11_db}
    └── extract_metrics(s11_data) → {center_frequency_ghz, bandwidth_mhz, vswr, return_loss_db, gain_dbi}
```

### Phase 5 — Result Posting (Feedback Loop)

```
FeedbackWorker
    ├── Build result_payload:
    │       {
    │           session_id, trace_id, design_id, iteration_index,
    │           metrics: {center_freq, bandwidth, s11_min, vswr, gain, efficiency},
    │           artifacts: {s11_file, farfield_file, metrics_file},
    │           execution_log: [...]
    │       }
    │
    ├── ApiClient.send_result(result_payload)
    │       └── ServerConnector.post("/api/v1/result", json=payload)
    │                   ← Server response: {status: "completed" | "refining", next_package?}
    │
    └── If status == "refining":
            → go back to Phase 3 with the new command_package
        If status == "completed":
            → SessionStore marks session as "completed"
            → UI shows final results
```

### Phase 6 — Session Persistence

At every stage, `SessionStore` saves a JSON snapshot to `test_checkpoints/{session_id}.json`. The `CheckpointManager` can save/restore mid-execution state for crash recovery.

---

## Server API Contract

The client expects the remote `antenna_server` to expose these REST endpoints:

| Endpoint | Method | Client Schema | Server Schema |
|----------|--------|--------------|---------------|
| `/api/v1/health` | GET | — | `{status, ann_status, llm_status, ann_message?, llm_message?}` |
| `/api/v1/capabilities` | GET | — | capability catalog dict |
| `/api/v1/optimize` | POST | `OptimizeRequest` (schema_version, user_request, target_spec, design_constraints, optimization_policy, runtime_preferences, client_capabilities, session_id?) | `OptimizeResponse` (status, session_id, trace_id, ann_prediction, command_package, clarification?, error?) |
| `/api/v1/result` | POST | result payload (session_id, trace_id, design_id, metrics, artifacts) | `{status: "completed" \| "refining", next_package?}` |
| `/api/v1/chat` | POST | `{message, requirements?}` | `{reply, updated_requirements?}` |
| `/api/v1/intent/parse` | POST | `{user_request}` | `{intent_summary}` |
| `/api/v1/sessions/{id}` | GET | — | session state dict |
| `ws://.../sessions/{id}/stream` | WebSocket | — | event stream `{event_type, data}` |

**Supported antenna families:** `microstrip_patch`, `amc_patch`, `wban_patch`

**Command package schema versions accepted:** `cst_command_package.v1`, `cst_command_package.v2`

---

## CST Studio Integration

The client integrates with **CST Studio Suite 2024** via the official CST Python API (COM interface, Windows-only). The integration flow:

1. `CSTApp.connect()` imports the `cst` package (installed alongside CST Studio) and calls `cst.interface.DesignEnvironment()` to attach to an already-running CST process. If no process is found, it attempts to launch `CST DESIGN ENVIRONMENT.exe` from the configured path.
2. The active 3D project handle (`mws`) is retrieved via `app.active_project().model3d`.
3. Every CST operation is serialized as a **VBA macro string** and injected via `mws.add_to_history(title, vba)`. This method appends the VBA block to the project's history list (the "navigation tree" in CST).
4. `mws.full_history_rebuild()` triggers CST to re-execute the entire history from top to bottom, applying the new commands.
5. Exported result files are read from the file system (CST writes them to the configured project directory).

**Why VBA macros instead of direct Python API calls?**
The CST Python API surface is limited. VBA macros can access the full CST object model (materials, solids, ports, boundary conditions, solver settings, monitors) with no restrictions. Every documented CST VBA object (`Brick`, `Material`, `Port`, `Solver`, `FarfieldMonitor`, etc.) is accessible via `mws.add_to_history`. The client uses a template-based approach — one `.vba` file per CST command type — to keep macro generation maintainable, testable, and auditable.

---

## VBA Template Catalog

Templates live in `src/executor/templates/`. Each file is a VBA snippet corresponding to one server command type:

| Template | CST Operation |
|----------|--------------|
| `cmd_create_project.vba` | Initialize a new CST project |
| `cmd_set_units.vba` | Set geometry and frequency units |
| `cmd_set_frequency_range.vba` | Configure solver frequency band |
| `cmd_define_material.vba` | Define material with ε, μ, σ, tan δ |
| `cmd_create_substrate.vba` | Create substrate brick (dielectric layer) |
| `cmd_create_ground_plane.vba` | Create ground plane (conductor brick) |
| `cmd_create_patch.vba` | Create radiating patch element |
| `cmd_create_feedline.vba` | Create microstrip feed line |
| `cmd_create_port.vba` | Define discrete port (wave port) |
| `cmd_define_parameter.vba` | Define a CST named parameter |
| `cmd_update_parameter.vba` | Update an existing CST parameter value |
| `cmd_define_brick.vba` | Define an arbitrary rectangular solid |
| `cmd_define_cone.vba` | Define a cone/truncated cone |
| `cmd_define_cylinder.vba` | Define a cylinder |
| `cmd_define_ecylinder.vba` | Define an elliptical cylinder |
| `cmd_define_sphere.vba` | Define a sphere |
| `cmd_define_torus.vba` | Define a torus |
| `cmd_define_extrude.vba` | Extrude a 2D profile |
| `cmd_define_loft.vba` | Loft between profiles |
| `cmd_define_rotate.vba` | Rotate solid around an axis |
| `cmd_boolean_add.vba` | Boolean union of two solids |
| `cmd_boolean_subtract.vba` | Boolean subtraction |
| `cmd_boolean_insert.vba` | Boolean insert (cut with keepout) |
| `cmd_boolean_intersect.vba` | Boolean intersection |
| `cmd_pick_face.vba` | Pick a face for port/operation targeting |
| `cmd_pick_edge.vba` | Pick an edge |
| `cmd_pick_endpoint.vba` | Pick an endpoint |
| `cmd_rebuild_model.vba` | Force full model history rebuild |
| `cmd_run_solver.vba` | Start the transient/frequency solver |
| `cmd_export_s11.vba` | Export S11/S-parameters to file |
| `cmd_calculate_port_extension_coefficient.vba` | Calculate port extension coefficient |
| `cmd_create_component.vba` | Create a new component/group in the model tree |
| `cmd_create_feedline.vba` | Create microstrip/coaxial feed |

---

## Session Lifecycle

```
┌──────────────┐
│   Created    │  Session created on first optimize response
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Active     │  Command package received; execution in progress
└──────┬───────┘
       │  (on pause)
       ▼
┌──────────────┐
│   Paused     │  User paused; execution halted between commands
└──────┬───────┘
       │  (on resume)
       ▼
┌──────────────┐
│   Active     │  Execution resumes from where it paused
└──────┬───────┘
       │  (on server: status = "completed")
       ▼
┌──────────────┐
│  Completed   │  Final metrics accepted; session archived
└──────────────┘

  (on any unrecoverable error)
       ▼
┌──────────────┐
│   Failed     │  Error logged; checkpoint saved for replay
└──────────────┘
```

JSON snapshots at `test_checkpoints/{session_id}.json` are written on every status transition.

---

## Offline / Dry-Run Mode

If `CSTApp.connect()` returns `False` (CST not installed, non-Windows OS, or CST not running), `ExecutionEngine` sets `self.dry_run = True`. In dry-run mode:
- All VBA macros are generated normally and logged.
- No CST API calls are made.
- `ExecutionResult.success` is set to `True` with a `"[DRY RUN]"` prefix in the output.
- Artifact paths are recorded as if the files were written.

`IntentParser` provides local offline intent parsing when the server is unreachable, so the user can still receive basic parameter suggestions without a network connection.

`tools/prepare_offline_feedback.py` allows constructing a complete result payload from previously exported artifact files, useful when CST has already run but the result POST failed due to a network outage.

---

## Compatibility Note

The repository uses a `src/` layout. The root-level [main.py](../main.py) preserves the original `python main.py` launch command while loading the application from `src/main.py`. Both `src/` and the project root are added to `sys.path` so that `from comm.xxx import ...` and `from src.comm.xxx import ...` both work depending on context (direct run vs. installed package).

## Recent Integration Fix

The optimize request `runtime_preferences` must include `priority: "normal"`. This field is required by the server schema — its absence was the root cause of earlier `422 Unprocessable Entity` failures. `RequestBuilder` now always stamps this field.