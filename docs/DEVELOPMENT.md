# Development

## Running Tests

```bash
pytest tests -q
python scripts/run_integration_tests.py
```

Real-server validation uses the URL configured in [config.json](../config.json):

```bash
python scripts/run_real_integration_tests.py
python scripts/workflow_validation.py
```

## Utility Scripts

- `scripts/health_check.py`: verify server and CST availability.
- `scripts/verify_request.py`: inspect generated optimize payloads.
- `scripts/schema_comparison.py`: compare generated request shape against expected schema.
- `scripts/diagnose_server.py`: send a direct debug request to inspect server errors.
- `scripts/debug_schema_validation.py`: incremental request-shape debugging.

## Conventions

- Application code lives under `src/`.
- Tests live under `tests/unit` and `tests/integration`.
- Long-lived docs live in `docs/`; historical reports move to `docs/archive/`.
- Generated outputs belong under `artifacts/` or `logs/`, not at the repository root.

## Maintenance Notes

- Keep `config.json` as the single local runtime configuration file.
- Preserve the root `main.py` launcher so external instructions do not break.
- If new scripts import from application packages, they must add `src/` to `sys.path` or be run with `PYTHONPATH=src`.