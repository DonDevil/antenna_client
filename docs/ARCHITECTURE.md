# Architecture

## Layout

- `src/comm`: API client, request builder, response handling, WebSocket support, and startup helpers.
- `src/session`: session persistence, checkpoints, design state, and recovery logic.
- `src/executor`: CST command parsing, VBA generation, execution orchestration, and progress tracking.
- `src/cst_client`: CST application and project automation wrappers.
- `src/ui`: desktop UI widgets and main window.
- `src/utils`: logging, validation, constants, health checks, and message coordination.

## Runtime Flow

1. The UI or a script collects a user request.
2. `comm.request_builder` builds an optimize payload.
3. `comm.api_client` sends the request through `comm.server_connector`.
4. The response handler parses the server response and extracts the command package.
5. `executor` converts commands into CST actions and VBA.
6. `session` stores progress, iterations, and exported artifacts.

## Compatibility Note

The repository now uses a `src/` layout. A small root-level [main.py](../main.py) preserves the original launch command while loading the application from `src/`.

## Recent Integration Fix

The optimize request runtime preferences now include `priority: "normal"`, which was required by the server schema and was the root cause of the earlier `422 Unprocessable Entity` failures.