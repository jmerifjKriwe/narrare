# Deployment Guide — Narrare

> **Deployment and development environment configuration.**
> Location: `docs/development/deployment-guide.md`

## Dev Environment

### Prerequisites

- Docker and Docker Compose
- Python 3.14+
- Node.js 20+
- just (command runner)

### Local Services

```bash
# Start all services (postgres+pgvector, redis)
just dev-up

# Stop services
just dev-down

# View logs
just dev-logs
```

### Dev Servers

```bash
# Start API + frontend (hot reload)
just dev

# Stop: Ctrl+C sends SIGINT to both processes cleanly
```

`just dev` starts both the API (port 8000) and the frontend (port 3000)
in the background. Press **Ctrl+C** to stop — the trap handler ensures
both processes are terminated cleanly.

### Dev Container

The `.devcontainer/` configuration provides:
- Python 3.14 with all dependencies
- Node.js 20+ for frontend
- Pre-configured extensions
- Automatic service startup

## CI/CD Pipelines

### Workflow: CI (`.github/workflows/ci.yml`)

Runs on every push:
1. Linting (ruff, biome)
2. Architecture checks (`check_architecture.py`)
3. Unit tests
4. Integration tests
5. Build verification

### Workflow: Architecture (`.github/workflows/architecture.yml`)

Fast feedback on architecture violations:
- Runs `scripts/check_architecture.py`
- Fails on constraint violations
- ~30 second runtime

### Workflow: Release (`.github/workflows/release-please.yml`)

Automated versioning via **release-please**:
- Parses conventional commits
- Bumps version (major/minor/patch)
- Generates CHANGELOG.md
- Creates GitHub release

**Supported commit types:**
| Type | Section | Example |
|------|---------|---------|
| `feat:` | ✨ Features | `feat: add character arc editor` |
| `fix:` | 🐛 Bug Fixes | `fix: resolve session timeout` |
| `perf:` | ⚡ Performance | `perf: optimize prompt caching` |
| `refactor:` | ♻️ Refactoring | `refactor: extract auth service` |
| `docs:` | 📚 Documentation | `docs: update deployment guide` |
| `chore:`, `test:`, `ci:` | *(hidden)* | Maintenance (not in CHANGELOG) |

**Breaking changes:** Add `!` after type: `feat!: redesign prompt API` or add `BREAKING CHANGE:` footer.

### CI Pipeline Specification

7-job pipeline with staged execution:

| Job | Target | Commands |
|-----|--------|----------|
| `architecture-check` | <30s | `python scripts/check_architecture.py` |
| `lint` | <60s | `ruff check` + `ruff format --check` (Python) |
| `typecheck` | <2min | `pyright --strict` |
| `test-unit` | <5min | `pytest tests/unit/` |
| `test-integration` | <5min | `pytest tests/integration/` |
| `frontend` | <3min | `biome check` + `validate-i18n` + `pnpm type-check` + `pnpm test` + `pnpm build` |
| `security` | <60s | `bandit -r` + `pip-audit` |

**Job ordering:**

```
architecture-check → lint + typecheck (parallel) → test-unit → test-integration → frontend + security
```

Tests run only if lint and typecheck pass (saves CI minutes).

**PR merge requires ALL jobs green. No bypass.**

## Pre-commit Hooks

Local quality checks before push:

```bash
# Install hooks
just pre-commit-install

# Run manually
just pre-commit-run
```

9 hooks configured in `.pre-commit-config.yaml`:

| Hook | Stage | Command |
|------|-------|---------|
| `architecture-constraints` | pre-commit | `python scripts/check_architecture.py` |
| `ruff-lint` | pre-commit | `ruff check --fix` |
| `ruff-format` | pre-commit | `ruff format` |
| `pyright` | pre-commit | `pyright` (changed files) |
| `bandit` | pre-commit | `bandit -c pyproject.toml` |
| `conventional-commits` | commit-msg | `python scripts/check_commit_message.py` |
| `biome-frontend` | pre-commit | `npx biome check --write components/ app/ lib/` (from packages/web/) |
| `validate-i18n` | pre-commit | `npx tsx scripts/validate-i18n.ts` (from workspace root) |
| `typecheck-frontend` | pre-commit | `npx tsc --noEmit` (from packages/web/) |

```yaml
repos:
  - repo: local
    hooks:
      - id: architecture-constraints
        name: Architecture Constraints
        entry: python scripts/check_architecture.py
        language: python
        pass_filenames: false
        always_run: true

      - id: ruff-lint
        name: Ruff Lint
        entry: ruff check --fix
        language: python
        types: [python]

      - id: ruff-format
        name: Ruff Format
        entry: ruff format
        language: python
        types: [python]

      - id: pyright
        name: Pyright (changed files)
        entry: pyright
        language: python
        types: [python]
        pass_filenames: true

      - id: bandit
        name: Security (Bandit)
        entry: bandit -c pyproject.toml
        language: python
        types: [python]

      - id: conventional-commits
        name: Conventional Commits
        entry: python scripts/check_commit_message.py
        language: python
        stages: [commit-msg]

      - id: biome-frontend
        name: Biome (Frontend)
        entry: bash -c 'cd packages/web && npx biome check --write components/ app/ lib/'
        language: system
        types: [tsx]
        pass_filenames: false
        always_run: true
        stages: [pre-commit]

      - id: validate-i18n
        name: i18n Validation
        entry: bash -c 'cd /workspace && npx tsx scripts/validate-i18n.ts'
        language: system
        types: [tsx]
        pass_filenames: false
        always_run: true
        stages: [pre-commit]

      - id: typecheck-frontend
        name: TypeScript Check (Frontend)
        entry: bash -c 'cd packages/web && npx tsc --noEmit'
        language: system
        types: [tsx]
        pass_filenames: false
        always_run: true
        stages: [pre-commit]
```

## Architecture Checker

`scripts/check_architecture.py` enforces:
- RULE-01: LLM imports
- RULE-02: Prompt building
- RULE-04: File size limits
- RULE-06: Router purity
- RULE-11: Silent failures

## Justfile Command Catalog

All developer commands via `just`:

| Category | Command | Description |
|----------|---------|-------------|
| **Setup** | `dev-setup` | First-time setup: install deps, create .env, run migrations |
| | `generate-secret` | Generate a secure `SECRET_KEY` |
| **Development** | `dev` | Start all services (API + frontend + workers) |
| | `dev-api` | Start API only |
| | `dev-frontend` | Start frontend only |
| | `dev-worker` | Start background worker |
| **Database** | `db-migrate` | Run pending Alembic migrations |
| | `db-downgrade` | Roll back last migration |
| | `db-seed` | Seed development data |
| | `db-reset` | Drop and recreate dev database (dangerous) |
| **Testing** | `test` | Run all tests |
| | `test-unit` | Run unit tests only (fast) |
| | `test-integration` | Run integration tests (needs Docker) |
| | `test-cov` | Run with coverage report |
| **Quality** | `check` | Run all checks (architecture + lint + typecheck + security) |
| | `lint` | Run ruff lint + fix |
| | `format` | Run ruff format |
| | `typecheck` | Run pyright |
| **Release** | `release-dry-run` | Preview changelog for unreleased changes |

## Release Process

1. All commits follow conventional format
2. Merge to main triggers release-please
3. Version bumped automatically
4. CHANGELOG.md generated
5. GitHub release created

## Environment Variables

See `.env.example` for all required variables:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://narrare:narrare@localhost:5432/narrare_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# Auth
SECRET_KEY=<generate with: just generate-secret>
ENVIRONMENT=development

# AI Providers (at least one required)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
ZAI_API_KEY=
ZAI_BASE_URL=

# Ollama (local models)
OLLAMA_BASE_URL=http://localhost:11434

# Default Model
DEFAULT_LLM_MODEL=anthropic/claude-sonnet-4-5
```

### Dev Login

For local development, a pre-seeded dev user is available:

| Variable | Default |
|----------|---------|
| `DEV_LOGIN_ENABLED` | `true` (dev only) |
| `DEV_LOGIN_EMAIL` | `dev@narrare.dev` |
| `DEV_LOGIN_PASSWORD` | `narrare-dev` |

Created by `just dev-setup`. Never present in production.

## Docker Compose Dev Services

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_USER: narrare
      POSTGRES_PASSWORD: narrare
      POSTGRES_DB: narrare_dev
    ports: ["5432:5432"]
    volumes: [postgres_data:/var/lib/postgresql/data]

  redis:
    image: redis:8-alpine
    ports: ["6379:6379"]
```

| Service | Image | Port | Database |
|---------|-------|------|----------|
| PostgreSQL | `pgvector/pgvector:pg17` | 5432 | `narrare_dev` |
| Redis | `redis:8-alpine` | 6379 | — |

The application runs locally (not in Docker) for hot reload.

## Monitoring

- Application logs: structlog with JSON output
- Metrics: (TODO) Prometheus endpoint
- Tracing: (TODO) OpenTelemetry integration

> Maintained by: Deployment Agent
