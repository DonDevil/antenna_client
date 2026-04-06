# API

## Server Endpoints

- `GET /api/v1/health`: connectivity and service readiness.
- `GET /api/v1/capabilities`: server-supported antenna families and limits.
- `POST /api/v1/optimize`: submit a design request and receive an optimization response with command package.
- `POST /api/v1/client-feedback`: return execution feedback and refinement status.

## Optimize Request Shape

The client builds requests in `comm.request_builder` with these high-level sections:

- `schema_version`
- `user_request`
- `target_spec`
- `design_constraints`
- `optimization_policy`
- `runtime_preferences`
- `client_capabilities`

Required runtime preferences include:

- `require_explanations`
- `persist_artifacts`
- `llm_temperature`
- `timeout_budget_sec`
- `priority`

## Workflow

1. Check health.
2. Submit optimize request.
3. Execute returned CST command package.
4. Send client feedback.
5. Continue until the server returns completed status or a stop condition.