# Antenna System Block Diagrams (ASCII Style)

This file contains plain text, dashed block diagrams derived from [ARCHITECTURE.md](ARCHITECTURE.md).

## 1) Client-Side Block Diagram

```text
+--------------------------+
|      RF Engineer/User    |
+------------+-------------+
             |
             v
+--------------------------+
|      UI Layer (PySide6)  |
|--------------------------|
| MainWindow               |
| ChatWidget               |
| DesignPanel              |
| StatusBar                |
+------------+-------------+
             |
             v
+--------------------------+
| Workflow/Orchestration   |
|--------------------------|
| ChatMessageHandler       |
| HealthMonitor            |
| ConnectionChecker        |
+------------+-------------+
             |
             v
+--------------------------+
| Communication Layer      |
|--------------------------|
| ServerConnector (HTTP)   |
| ApiClient                |
| RequestBuilder           |
| ResponseHandler          |
| ErrorHandler             |
| WS SessionEventListener  |
| IntentParser (fallback)  |
+------------+-------------+
             |
             | OptimizeResponse / CommandPackage
             v
+--------------------------+
| Executor Layer           |
|--------------------------|
| CommandParser            |
| V2 Contract Validator    |
| ExecutionEngine          |
| VBAGenerator             |
+------------+-------------+
             |
             | VBA macros
             v
+--------------------------+
| CST Integration Layer    |
|--------------------------|
| CSTApp                   |
| VBAExecutor              |
| ProjectManager           |
| ResultExtractor          |
+------------+-------------+
             |
             v
+--------------------------+
| CST Studio Suite         |
| (local Windows machine)  |
+------------+-------------+
             |
             | export files / metrics
             v
+--------------------------+        +--------------------------+
| Session & Persistence    |<------>| Offline Calculation      |
|--------------------------|        | Tools                    |
| SessionStore             |        |--------------------------|
| CheckpointManager        |        | RectPatchCalculator      |
| DesignStore              |        | AMCCalculator            |
| DesignExporter           |        | WBANCalculator           |
| IterationTracker         |        +--------------------------+
| ChatHistory              |
+--------------------------+
```

## 2) Server-Side Block Diagram

```text
+---------------------------+
|       Antenna Client      |
+-------------+-------------+
              |
              | REST + WebSocket
              v
+---------------------------+
| Ingress Layer             |
|---------------------------|
| REST API                  |
| /health                   |
| /capabilities             |
| /chat                     |
| /intent/parse             |
| /optimize                 |
| /result                   |
|                           |
| WS /sessions/{id}/stream  |
+-------------+-------------+
              |
              v
+---------------------------+
| Application Services      |
|---------------------------|
| Health Service            |
| Capabilities Service      |
| Chat Service              |
| Intent Parse Service      |
| Optimize Orchestrator     |
| Result Ingestion Service  |
+-------------+-------------+
              |
              v
+---------------------------+
| AI/ML Core                |
|---------------------------|
| LLM Planner               |
| ANN Surrogate             |
| Policy/Constraint Engine  |
+-------------+-------------+
              |
              v
+---------------------------+
| Command + Iteration Core  |
|---------------------------|
| CST Command Builder       |
| Contract Validator        |
| Iteration Manager         |
+------+------+-------------+
       |      |
       |      +--------------------------+
       v                                 v
+---------------------------+   +---------------------------+
| Session/State Store       |   | Trace + Artifact Store    |
+-------------+-------------+   +-------------+-------------+
              |                               |
              +---------------+---------------+
                              v
+---------------------------+
| Outbound Layer            |
|---------------------------|
| OptimizeResponse          |
| Session Events            |
| (iteration/completion)    |
+-------------+-------------+
              |
              v
+---------------------------+
|       Antenna Client      |
+---------------------------+
```

## 3) End-to-End Flow Diagram (Separate)

```text
+------------------+     +--------------------+     +-------------------+
| User / UI        |     | Client Core        |     | antenna_server    |
+--------+---------+     +---------+----------+     +---------+---------+
         |                         |                          |
         | 1) user request         |                          |
         +------------------------>|                          |
         |                         |                          |
         |                         | 2) POST /chat            |
         |                         +------------------------->|
         |                         | 3) POST /intent/parse    |
         |                         +------------------------->|
         |                         |<-------------------------+
         |                         | chat + intent            |
         |                         |                          |
         |                         | 4) POST /optimize        |
         |                         +------------------------->|
         |                         |<-------------------------+
         |                         | OptimizeResponse +       |
         |                         | CommandPackage           |
         |                         |                          |
+--------+---------+     +---------+----------+     +---------+---------+
| ExecutionEngine  |<----+ 5) parse/validate  |     | Iteration Engine  |
+--------+---------+                                 +-------------------+
         |
         | 6) generate VBA per command
         v
+------------------+
| CST Studio       |
| add_to_history   |
| full_rebuild     |
| run_solver       |
+--------+---------+
         |
         | 7) export S11/farfield
         v
+------------------+
| ResultExtractor  |
+--------+---------+
         |
         | 8) metrics + artifacts
         v
+------------------+              +-------------------+
| Client Core      |-------------->| POST /result      |
+--------+---------+              +---------+---------+
         |                                  |
         |<---------------------------------+
         | 9) converged or next iteration
         |
         +--> if next iteration: repeat steps 5..9
         +--> if converged: show final summary in UI
```

## Optional

- If you want image exports too, these ASCII diagrams can be converted into PNG/SVG in a follow-up pass.
