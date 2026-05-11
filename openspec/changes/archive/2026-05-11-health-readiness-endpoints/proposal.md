## Why

The `/health` endpoint returns a hardcoded `{"status": "ok"}` regardless of whether the database is reachable. In production, this means orchestrators (Kubernetes, Docker Compose) SHALL NOT be able to detect when the API is unable to serve requests because the DB is down.

## What Changes

- Split health into two endpoints: **liveness** (`/health`) and **readiness** (`/ready`)
- `/health` MUST stay as-is — confirms the process is alive
- `/ready` MUST check database connectivity and return 503 if unreachable
- The system SHALL have full test coverage for both endpoints

## Capabilities

### New Capabilities
- `readiness-check`: Async DB connectivity check exposed at `GET /ready`, returns 200 with details or 503 on failure

### Modified Capabilities
- `health-check`: Clarified semantics — liveness only, MUST NOT check dependencies

## Impact

- `apps/api/narrare/metrics/router.py`: Add `/ready` endpoint with DB check
- `tests/unit/api/metrics/test_metrics_router.py`: New test file with full coverage
