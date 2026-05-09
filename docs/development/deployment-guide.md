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

### Dev Container

The `.devcontainer/` configuration provides:
- Python 3.14 with all dependencies
- Node.js 20+ for frontend
- Pre-configured extensions
- Automatic service startup

## CI/CD Pipelines

### Workflow: CI (`.github/workflows/ci.yml`)

Runs on every push:
1. Linting (ruff, mypy, eslint)
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

Automated versioning:
- Parses conventional commits
- Bumps version (major/minor/patch)
- Generates CHANGELOG.md
- Creates GitHub release

## Pre-commit Hooks

Local quality checks before push:

```bash
# Install hooks
just pre-commit-install

# Run manually
just pre-commit-run
```

Hooks include:
- Trailing whitespace check
- Line length check
- Architecture constraint check
- Python formatting (ruff)
- Type checking (mypy)

## Architecture Checker

`scripts/check_architecture.py` enforces:
- RULE-01: LLM imports
- RULE-02: Prompt building
- RULE-04: File size limits
- RULE-06: Router purity
- RULE-11: Silent failures

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
DATABASE_URL=postgresql+asyncpg://...

# Redis
REDIS_URL=redis://localhost:6379

# LLM Providers
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...

# Application
SECRET_KEY=...
ENVIRONMENT=development
```

## Monitoring

- Application logs: structlog with JSON output
- Metrics: (TODO) Prometheus endpoint
- Tracing: (TODO) OpenTelemetry integration

> Maintained by: Deployment Agent
