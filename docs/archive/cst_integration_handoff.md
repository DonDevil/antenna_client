# Client Integration Handoff Guide

This document is for the **client-side Copilot / frontend or CST-automation implementation** that needs to communicate correctly with the `antenna_server` backend.

---

## 1) What this server actually does

The server is responsible for:

- parsing user intent from natural language
- validating design requirements
- predicting initial antenna geometry with the **ANN**
- generating a **high-level CST command package**
- receiving simulation feedback and deciding whether to refine or stop

The server does **not**:

- execute CST itself
- send raw VBA macros
- manage CST windows or file exports on the client machine

> The **client side** must execute the CST actions, collect outputs/metrics, and send feedback back to the server.

---

## 2) Recommended client architecture

Use a structure similar to this:

```text
client/
  src/
    api/
      httpClient.ts          # fetch/axios wrapper
      endpoints.ts           # typed REST calls
      wsClient.ts            # websocket subscription helper
    orchestrator/
      pipelineController.ts  # end-to-end optimize -> execute -> feedback loop
    services/
      cstCommandExecutor.ts  # translates command_package.commands to CST actions
      feedbackBuilder.ts     # builds POST /client-feedback payload
    state/
      sessionStore.ts        # local UI/session state
    types/
      server.ts              # request/response interfaces matching backend
      cst.ts                 # local CST execution result types
```

### Client responsibilities

1. Maintain **connection state** to the backend.
2. Maintain **session state** locally after `/optimize` returns `session_id`.
3. Execute server-provided CST commands **in order**.
4. Collect:
   - S11 results
   - bandwidth / center frequency / gain / VSWR
   - artifact references / exported file paths
5. Post feedback to the backend.
6. If refinement is returned, repeat the loop.

---

## 3) Important lifecycle rule

### Session creation rule

A design session is effectively created when the client calls:

- `POST /api/v1/optimize`

The WebSocket endpoint **does not create** the session by itself. It only streams updates for an **existing** `session_id`.

---

## 4) Base URL and transport

Default local server:

```text
http://localhost:8000
```

Base API prefix:

```text
/api/v1
```

Transports used:

- **HTTP REST** for request/response operations
- **WebSocket** for live session updates

No authentication is currently implemented in the backend.
CORS is currently open (`*`).

---

## 5) Recommended client startup flow

On client app start:

1. call `GET /api/v1/health`
2. poll until startup warm-up finishes if needed
3. optionally call `GET /api/v1/capabilities`
4. show the user what the server currently supports

### Health handling rules

The server now reports these statuses:

- `ann_status`: `available` | `loading` | `none`
- `llm_status`: `available` | `loading` | `none`

Recommended behavior:

- if `status != "ok"`: backend is unavailable
- if `llm_status == "loading"`: show **"LLM warming up..."**
- if `llm_status == "none"`: disable chat-heavy UX or use fallback mode
- if `ann_status == "none"`: warn user that prediction may fall back or fail
- if both are `available`: full pipeline is ready

---

## 6) Full communication flow

### A. Conversational requirement capture (optional)

Use:

- `POST /api/v1/chat`
- `POST /api/v1/intent/parse`

Purpose:

- extract `frequency_ghz`
- extract `bandwidth_mhz`
- extract `antenna_family`
- guide the user to supply missing data

### B. Optimization start (required)

Use:

- `POST /api/v1/optimize`

Purpose:

- create or resume a session
- get ANN prediction
- get CST command package

### C. Live monitoring (optional but recommended)

Use:

- `WS /api/v1/sessions/{session_id}/stream`

Purpose:

- receive session progress updates
- receive iteration completion / final state notifications

### D. CST execution and feedback loop

1. execute `command_package.commands`
2. export results
3. send `POST /api/v1/client-feedback`
4. if server returns another command package, execute again
5. stop when server returns completed or stop condition

---

## 7) All available endpoints

| Method | Endpoint | Purpose | Typical Client Use |
|---|---|---|---|
| `GET` | `/api/v1/health` | Server and dependency readiness | Poll on startup / reconnect |
| `GET` | `/api/v1/capabilities` | Supported frequency/material/family capabilities | Populate UI constraints |
| `POST` | `/api/v1/intent/parse` | Parse natural language into structured intent summary | Fast requirement extraction |
| `POST` | `/api/v1/chat` | Chat assistant for capability questions and requirement capture | Conversational UI |
| `POST` | `/api/v1/optimize` | Start or resume optimization session | Main pipeline entrypoint |
| `POST` | `/api/v1/client-feedback` | Return CST simulation results to server | Iteration loop |
| `GET` | `/api/v1/sessions/{session_id}` | Fetch saved session state and progress | Recovery / reload / debugging |
| `WS` | `/api/v1/sessions/{session_id}/stream` | Stream session events | Live progress UI |

---

## 8) Endpoint details and usage

### `GET /api/v1/health`

Use this before showing the main UI as ready.

#### Example response

```json
{
  "status": "ok",
  "service": "AMC Antenna Optimization Server",
  "version": "0.1.0",
  "ann_model_ready": true,
  "ann_model_loaded": true,
  "ann_status": "available",
  "ann_model_version": "v1",
  "llm_status": "available",
  "llm_model": "deepseek-r1:8b",
  "ollama_base_url": "http://localhost:11434",
  "ollama_reachable": true,
  "ann_message": "ann_model_loaded",
  "llm_message": "llm_ready"
}
```

#### Notes

- `loading` means warm-up is in progress.
- `none` means not yet available or unreachable.
- `GET /health` may itself trigger/continue warm-up logic.

---

### `GET /api/v1/capabilities`

Use this to know valid operating ranges and options before building the request UI.

#### Purpose

- show supported antenna families
- show supported materials and substrates
- validate user ranges on the client before POSTing `/optimize`

---

### `POST /api/v1/intent/parse`

Use this for a simple parse-only operation.

#### Request

```json
{
  "user_request": "Design a microstrip patch antenna at 2.45 GHz with 100 MHz bandwidth"
}
```

#### Response

```json
{
  "status": "ok",
  "intent_summary": {
    "summary_version": "intent_summary.v1",
    "raw_request": "Design a microstrip patch antenna at 2.45 GHz with 100 MHz bandwidth",
    "parsed_frequency_ghz": 2.45,
    "parsed_bandwidth_mhz": 100.0,
    "parsed_antenna_family": "microstrip_patch",
    "missing_fields": [],
    "llm_intent": {
      "source": "llm"
    }
  }
}
```

#### When to use

- quick extraction from natural language
- pre-filling the optimize form
- validating if the user request is complete enough

---

### `POST /api/v1/chat`

Use this for the conversational assistant UX.

#### Request

```json
{
  "message": "I want a rectangular patch around 2.45 GHz.",
  "requirements": {
    "frequency_ghz": null,
    "bandwidth_mhz": null,
    "antenna_family": null
  }
}
```

#### Response shape

```json
{
  "status": "ok",
  "assistant_message": "...",
  "intent_summary": { "...": "..." },
  "requirements": {
    "frequency_ghz": 2.45,
    "bandwidth_mhz": null,
    "antenna_family": "microstrip_patch"
  },
  "supported_families": ["amc_patch", "microstrip_patch", "wban_patch"],
  "capabilities": {
    "frequency_range_ghz": { "min": 0.5, "max": 10.0 },
    "bandwidth_range_mhz": { "min": 5.0, "max": 2000.0 },
    "available_conductor_materials": ["Copper (annealed)"],
    "available_substrate_materials": ["FR-4 (lossy)"]
  }
}
```

#### When to use

- user-facing chat assistant
- requirement gathering before `/optimize`
- answering capability/material/family questions

> Use `/chat` for UX assistance, but use `/optimize` for the real optimization job.

---

### `POST /api/v1/optimize`

This is the **main entrypoint** for the full pipeline.

#### Minimal recommended request

```json
{
  "schema_version": "optimize_request.v1",
  "session_id": null,
  "user_request": "Design a microstrip patch antenna for 2.45 GHz with 100 MHz bandwidth.",
  "target_spec": {
    "frequency_ghz": 2.45,
    "bandwidth_mhz": 100.0,
    "antenna_family": "microstrip_patch"
  },
  "design_constraints": {
    "allowed_materials": ["Copper (annealed)"],
    "allowed_substrates": ["FR-4 (lossy)"]
  },
  "optimization_policy": {
    "mode": "auto_iterate",
    "max_iterations": 5,
    "stop_on_first_valid": true,
    "acceptance": {
      "center_tolerance_mhz": 20.0,
      "minimum_bandwidth_mhz": 10.0,
      "maximum_vswr": 2.0,
      "minimum_gain_dbi": 0.0
    },
    "fallback_behavior": "best_effort"
  },
  "runtime_preferences": {
    "require_explanations": false,
    "persist_artifacts": true,
    "llm_temperature": 0.0,
    "timeout_budget_sec": 300
  },
  "client_capabilities": {
    "supports_farfield_export": true,
    "supports_current_distribution_export": false,
    "supports_parameter_sweep": false,
    "max_simulation_timeout_sec": 600,
    "export_formats": ["json"]
  }
}
```

#### Expected success response

```json
{
  "schema_version": "optimize_response.v1",
  "status": "accepted",
  "session_id": "<uuid>",
  "trace_id": "<uuid>",
  "current_stage": "planning_commands",
  "ann_prediction": {
    "ann_model_version": "v1",
    "confidence": 0.8,
    "dimensions": {
      "patch_length_mm": 30.2,
      "patch_width_mm": 38.1,
      "patch_height_mm": 0.035,
      "substrate_length_mm": 45.0,
      "substrate_width_mm": 50.0,
      "substrate_height_mm": 1.6,
      "feed_length_mm": 12.0,
      "feed_width_mm": 3.0,
      "feed_offset_x_mm": 0.0,
      "feed_offset_y_mm": -6.0
    }
  },
  "command_package": {
    "schema_version": "cst_command_package.v1",
    "session_id": "<uuid>",
    "trace_id": "<uuid>",
    "design_id": "design_<session_id>",
    "iteration_index": 0,
    "commands": [
      { "seq": 1, "command": "create_project", "params": { "project_name": "design_<session_id>" } }
    ]
  },
  "warnings": []
}
```

#### Client rules

- Save `session_id` immediately.
- Save `trace_id` immediately.
- Save `design_id` from `command_package`.
- Execute commands **exactly in order**.
- Do not invent additional CST actions unless your client explicitly needs local helper steps.

#### If response is `clarification_required`

Prompt the user for missing or conflicting inputs and do **not** start CST execution.

#### If response is `error`

Show the error and stop the pipeline.

---

### `POST /api/v1/client-feedback`

This is called **after the client executes the CST simulation**.

#### Required payload

```json
{
  "schema_version": "client_feedback.v1",
  "session_id": "<uuid>",
  "trace_id": "<uuid>",
  "design_id": "design_<session_id>",
  "iteration_index": 0,
  "simulation_status": "completed",
  "actual_center_frequency_ghz": 2.44,
  "actual_bandwidth_mhz": 92.0,
  "actual_return_loss_db": -18.5,
  "actual_vswr": 1.45,
  "actual_gain_dbi": 4.8,
  "notes": "Initial CST run completed successfully.",
  "artifacts": {
    "s11_trace_ref": "C:/exports/s11_iteration_0.csv",
    "farfield_ref": "C:/exports/farfield_iteration_0.json",
    "current_distribution_ref": null,
    "summary_metrics_ref": "C:/exports/summary_iteration_0.json"
  }
}
```

#### Response outcomes

##### If accepted

```json
{
  "status": "completed",
  "accepted": true,
  "message": "Acceptance criteria met. No further refinement needed."
}
```

##### If refinement is needed

```json
{
  "status": "refining",
  "accepted": false,
  "iteration_index": 1,
  "planning_summary": {
    "selected_action": "...",
    "decision_source": "deterministic_rule"
  },
  "next_command_package": { "...": "..." }
}
```

#### Important client rule

If `next_command_package` exists, the client should:

1. update the current iteration index
2. execute the new command package
3. gather results again
4. submit another `/client-feedback`

> This is the main refinement loop.

---

### `GET /api/v1/sessions/{session_id}`

Use this when:

- reloading the UI
- recovering from app restart
- showing current backend state
- debugging

#### Typical response fields

- `session_id`
- `status`
- `stop_reason`
- `current_iteration`
- `max_iterations`
- `intent_summary`
- `surrogate_validation`
- `policy_runtime`
- `latest_planning_decision`
- `history_count`
- `latest_entry`

---

### `WS /api/v1/sessions/{session_id}/stream`

Use this for live progress UI.

#### Example URL

```text
ws://localhost:8000/api/v1/sessions/<session_id>/stream
```

#### Event schema

Each event uses `schema_version: "session_event.v1"`.

Possible event types in schema:

- `session.accepted`
- `stage.changed`
- `llm.intent.parsed`
- `ann.prediction.ready`
- `command.package.ready`
- `client.feedback.received`
- `iteration.completed`
- `session.completed`
- `session.failed`

#### Important current implementation note

The current backend mainly emits:

- `iteration.completed`
- `session.completed`
- `session.failed`

So the client should:

- support the full schema generically
- but not depend on every event type always being emitted

#### Typical event example

```json
{
  "schema_version": "session_event.v1",
  "event_type": "iteration.completed",
  "session_id": "<uuid>",
  "trace_id": "<uuid>",
  "iteration_index": 1,
  "timestamp": "2026-04-06T12:00:00Z",
  "payload": {
    "stage": "refining_design",
    "message": "Session history updated",
    "accepted": false
  }
}
```

---

## 9) High-level CST command package contract

The server sends a `command_package` that contains a safe ordered list of actions such as:

1. `create_project`
2. `set_units`
3. `set_frequency_range`
4. `define_material`
5. `create_substrate`
6. `create_ground_plane`
7. `create_patch`
8. `create_feedline`
9. `create_port`
10. `set_boundary`
11. `set_solver`
12. `run_simulation`
13. `export_s_parameters`
14. `extract_summary_metrics`
15. `export_farfield` (if supported)

### Client rule

The client-side CST layer should map each `command` to a local CST automation function.

Example mapping idea:

```ts
const handlers = {
  create_project: createProject,
  set_units: setUnits,
  set_frequency_range: setFrequencyRange,
  define_material: defineMaterial,
  create_substrate: createSubstrate,
  create_ground_plane: createGroundPlane,
  create_patch: createPatch,
  create_feedline: createFeedline,
  create_port: createPort,
  set_boundary: setBoundary,
  set_solver: setSolver,
  run_simulation: runSimulation,
  export_s_parameters: exportSParameters,
  extract_summary_metrics: extractSummaryMetrics,
  export_farfield: exportFarfield,
}
```

Do **not** expect VBA from the server.
The client must translate these high-level commands into CST automation locally.

---

## 10) Error handling requirements

The client should explicitly handle these cases:

### HTTP 422 validation errors
Common codes:

- `SCHEMA_VALIDATION_FAILED`
- `FAMILY_NOT_SUPPORTED`
- `FAMILY_PROFILE_CONSTRAINT_FAILED`
- `INVALID_INTENT_REQUEST`
- `INVALID_CHAT_REQUEST`

### Feedback/session errors
Common codes:

- `SESSION_NOT_FOUND`
- `FEEDBACK_PROCESSING_FAILED`

### Surrogate or policy rejection
Possible optimize error details can include:

- `LOW_SURROGATE_CONFIDENCE`

### UX behavior

- show the server message directly
- allow user correction and retry
- preserve local draft form values
- keep `session_id` only if a valid optimize response created one

---

## 11) Recommended client state machine

```text
idle
  -> checking_health
  -> collecting_requirements
  -> optimizing
  -> session_created
  -> executing_cst
  -> sending_feedback
  -> refining (loop to executing_cst)
  -> completed
  -> failed
```

### Important local state to keep

```ts
type ClientSessionState = {
  backendStatus: "ok" | "down"
  annStatus: "available" | "loading" | "none"
  llmStatus: "available" | "loading" | "none"
  sessionId?: string
  traceId?: string
  designId?: string
  currentIteration: number
  latestCommandPackage?: unknown
  latestMetrics?: unknown
  phase:
    | "idle"
    | "collecting_requirements"
    | "optimizing"
    | "executing"
    | "sending_feedback"
    | "refining"
    | "completed"
    | "failed"
}
```

---

## 12) Best-practice integration sequence

### Recommended sequence for the client app

1. `GET /api/v1/health`
2. If needed, wait until warm-up completes
3. `GET /api/v1/capabilities`
4. optional: `POST /api/v1/chat` or `POST /api/v1/intent/parse`
5. `POST /api/v1/optimize`
6. Save `session_id`, `trace_id`, `design_id`
7. Connect WebSocket using `session_id`
8. Execute `command_package.commands`
9. Export CST results and files
10. `POST /api/v1/client-feedback`
11. If `next_command_package` returned, repeat from step 8
12. Stop when `status == completed` or server stops the session

---

## 13) Important implementation notes for the client-side Copilot

### Must do

- use the server-generated `session_id`
- use the server-generated `trace_id`
- execute commands in order
- send back feedback after each CST run
- support both REST and WebSocket
- handle warm-up and dependency status from `/health`
- gracefully handle `clarification_required` and `error`

### Must not do

- do not assume WebSocket creates a session
- do not invent raw VBA payloads to send to the backend
- do not skip the feedback loop
- do not assume the LLM is always immediately available at startup
- do not assume every documented WebSocket event type is emitted today

---

## 14) Suggested client prompts for Copilot

If you use Copilot on the client project, a good implementation prompt is:

> Build a client for the AMC Antenna Optimization Server. Use the endpoints documented in `docs/client_integration_handoff.md`. Implement a typed API client, session store, WebSocket listener, CST command executor adapter, and an optimize-feedback refinement loop. Respect `session_id`, `trace_id`, `design_id`, health states (`available/loading/none`), and the command package ordering.

---

## 15) Summary

For the client side, the main rule is:

> **Use chat/intent endpoints to gather inputs, use `/optimize` to start the real session, execute the returned CST commands locally, and use `/client-feedback` to continue the refinement loop.**

That is the correct integration model for this backend.
