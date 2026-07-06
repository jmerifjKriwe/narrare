<!-- Context: narrare-dev/guides/deployment | Priority: high | Source: docs/development/deployment-guide.md | Updated: 2026-07-06 -->

# Deployment & Dev Environment

> Complete reference: `docs/development/deployment-guide.md`

## Dev Environment Setup

**Prerequisites:** Docker + Docker Compose, Python 3.14+, Node.js 24+, just (command runner)

```bash
just dev-setup    # First-time: install dev + NLP deps/models, create .env, run migrations
just dev          # Start API (port 8000) + frontend (port 3000) + workers (auto-starts PostgreSQL + Redis via _ensure-services)
just dev-services # Start backing Docker services only (PostgreSQL pgvector:pg17 + Redis 8-alpine) — use this when you want the DBs without the app
```

> **No `just dev-up`.** There is no separate `dev-up` recipe. `just dev` already ensures
> PostgreSQL + Redis are running via `_ensure-services`; for a pure service start use
> `just dev-services`, and stop them with `just dev-services-stop`.

Auto-migration: API runs `alembic upgrade head` on every startup via `lifespan.py`.

## Docker Compose Dev Services

| Service | Image | Port | Database |
|---------|-------|------|----------|
| PostgreSQL | `pgvector/pgvector:pg17` | 5432 | `narrare_dev` |
| Redis | `redis:8-alpine` | 6379 | — |

App runs locally (not in Docker) for hot reload.

## CI Pipeline

> Authoritative source: `.github/workflows/ci.yml` — read it for the current job list
> (e.g. architecture, lint, typecheck, security, test-unit, test-integration,
> update-coverage-badge, frontend, test-e2e, warnings-summary) and ordering. The job
> count and set below can drift; do not rely on the number of jobs shown here.

| Job | Target | Commands |
|-----|--------|----------|
| `architecture-check` | <30s | `python scripts/check_architecture.py` |
| `lint` | <60s | `ruff check` + `ruff format --check` |
| `typecheck` | <2min | `pyright --strict` |
| `test-unit` | <5min | `pytest tests/unit/` |
| `test-integration` | <5min | `pytest tests/integration/` |
| `frontend` | <3min | biome + validate-i18n + tsc + pnpm test + build |
| `security` | <60s | `bandit -r` + `pip-audit` |

**Ordering:** architecture → lint + typecheck (parallel) → unit → integration → frontend + security. PR merge requires ALL green.

## Pre-commit Hooks

> Authoritative source: `.pre-commit-config.yaml` — see it for the current hook list,
> and run `pre-commit run --all-files` for the live set. The hook count and list below
> can drift; do not rely on the number shown here.

| Hook | Stage | What it runs |
|------|-------|--------------|
| `architecture-constraints` | pre-commit | `check_architecture.py` (RULE-01/02/04/06/11) |
| `ruff-lint` | pre-commit | `ruff check --fix` |
| `ruff-format` | pre-commit | `ruff format` |
| `pyright` | pre-commit | Type checking on changed files |
| `bandit` | pre-commit | Security linting |
| `conventional-commits` | commit-msg | Commit message format validation |
| `biome-frontend` | pre-commit | Frontend lint/format |
| `validate-i18n` | pre-commit | i18n key consistency |
| `typecheck-frontend` | pre-commit | `tsc --noEmit` |

## Architecture Checker

`scripts/check_architecture.py` enforces: RULE-01 (LLM imports), RULE-02 (prompt building), RULE-04 (file size), RULE-06 (router purity), RULE-11 (silent failures).

## Release Process

1. All commits follow conventional format (`feat:`, `fix:`, `perf:`, etc.)
2. Merge to main triggers release-please
3. Version bumped automatically, CHANGELOG.md generated
4. GitHub release created with Docker image + release bundle

**Docker deployment:** Single image (`ghcr.io/<owner>/narrare:<version>`) with API + frontend. Next.js on :3000 proxies `/api/v1/*` to FastAPI on :8000.

## Environment Variables

| Variable | Required | Notes |
|----------|----------|-------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://narrare:narrare@localhost:5432/narrare_dev` |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` |
| `SECRET_KEY` | Yes | Generate with `just generate-secret` |
| `NARRARE_ENCRYPTION_KEY` | Yes | Fernet key for user API keys. **Lost = unrecoverable** |
| AI API key | At least one | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `ZAI_API_KEY`, etc. |
| `DEFAULT_LLM_MODEL` | No | Default: `anthropic/claude-sonnet-4-5` |

## Dev Login

| Variable | Default |
|----------|---------|
| `DEV_LOGIN_ENABLED` | `true` (dev only) |
| `DEV_LOGIN_EMAIL` | `dev@narrare.dev` |
| `DEV_LOGIN_PASSWORD` | `narrare-dev` |

**Related**: `narrare-dev/lookup/justfile-commands`, `narrare-dev/lookup/tech-stack`
