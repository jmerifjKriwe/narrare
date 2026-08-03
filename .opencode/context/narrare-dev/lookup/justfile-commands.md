<!-- Context: narrare-dev/lookup/justfile-commands | Priority: critical | Source: docs/development/deployment-guide.md | Updated: 2026-07-06 -->

# Justfile Command Catalog

> Complete reference: `docs/development/deployment-guide.md`

## Setup

| Command | Description |
|---------|-------------|
| `just dev-setup` | First-time setup: install dev + NLP deps/models, create .env, run migrations |
| `just generate-secret` | Generate a secure `SECRET_KEY` |

## Development

| Command | Description |
|---------|-------------|
| `just dev` | Start all services (API + frontend + workers). Internally calls `_ensure-services`, so PostgreSQL + Redis are brought up automatically |
| `just dev-api` | Start API only |
| `just dev-frontend` | Start frontend only |
| `just dev-worker` | Start background worker |
| `just dev-services` | Start Docker services only (PostgreSQL + Redis). Use this when you want the backing services without the app |
| `just dev-services-stop` | Stop Docker services |
| `just logs` | Tail Docker service logs |

> **No `just dev-up`.** There is no separate `dev-up` recipe. `just dev` already ensures backing services via `_ensure-services`; for a pure service start use `just dev-services`.

## Database

| Command | Description |
|---------|-------------|
| `just db-migrate` | Run pending Alembic migrations (optional — auto-runs on startup) |
| `just db-downgrade` | Roll back last migration |
| `just db-seed` | Seed development data |
| `just db-reset` | Drop and recreate dev database (dangerous) |

## Testing

| Command | Description |
|---------|-------------|
| `just test` | Run all tests |
| `just test-unit` | Run unit tests only (fast) |
| `just test-integration` | Run integration tests (needs Docker) |
| `just test-cov` | Run with coverage report |
| `just test-file <path>` | Run tests for a specific file |

## Quality

| Command | Description |
|---------|-------------|
| `just check` | Run all checks (architecture + lint + typecheck + security) |
| `just check-verbose` | Run all checks with full tool output |
| `just check-architecture` | Run architecture constraints + exception baseline |
| `just check-adoption` | Validate static + runtime AI adoption and ratchet governed debt |
| `just check-exceptions` | Ensure approved architecture exceptions do not grow |
| `just check-frontend-size` | Check TS/TSX RULE-04 file-size no-growth gate |
| `just check-streaming` | Check RULE-20 SSE frontend coverage for backend streaming endpoints |
| `just check-prompts-strict` | Run prompt structure checker with warnings treated as failures |
| `just lint` | Run ruff lint + fix |
| `just format` | Run ruff format |
| `just typecheck` | Run pyright |

## Pre-commit

| Command | Description |
|---------|-------------|
| `just pre-commit-install` | Install pre-commit hooks |
| `just pre-commit-run` | Run all pre-commit hooks manually |

## Release

| Command | Description |
|---------|-------------|
| `just release-dry-run` | Preview changelog for unreleased changes |

**Related**: `narrare-dev/guides/deployment`, `narrare-dev/lookup/tech-stack`
