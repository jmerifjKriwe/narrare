# Deployment Guide — Narrare

> **Deployment and development environment configuration.**
> Location: `docs/development/deployment-guide.md`

## Dev Environment

### Prerequisites

- Docker and Docker Compose
- Python 3.14+
- Node.js 24+
- just (command runner)

### Python Environment Setup

The project uses `uv` with workspace members (`apps/api`, `packages/core`, `packages/i18n`). To set up the Python environment:

```bash
# Install all dependencies AND workspace member packages
uv sync --all-packages
```

**Important:** `uv sync` alone does NOT install workspace member packages (narrare, narrare_core) in editable mode. You MUST use `--all-packages` to make workspace members importable. Without this:
- Pre-commit hooks fail (OpenAPI spec regeneration: `No module named 'narrare'`)
- Pyright reports thousands of unresolved imports
- Running `uv run python` cannot import `narrare` or `narrare_core`

**Verification:**

```bash
uv run python -c "import narrare_core; import narrare; print('OK')"
```

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
```

`just dev` starts both the API (port 8000) and the frontend (port 3000)
in the background. Press **Ctrl+C** to stop — all processes (API, frontend,
and their children) are terminated cleanly. You'll see "⏹ Shutting down…"
followed by "⏹ Stopped." when complete.

**Auto-migration:** The API runs `alembic upgrade head` automatically on every
startup (via `lifespan.py`). You do not need to run migrations manually for
normal development. The current schema version is logged at startup. If
migrations fail, the app fails to start — check the terminal output for details.

### Dev Container

The `.devcontainer/` configuration provides:
- Python 3.14 with all dependencies
- Node.js 24+ for frontend
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
| `architecture-check` | <30s | `python scripts/check_architecture.py` + `check_exception_baseline.py` + `check_adoption.py` + `check_prompt_structure.py` + `check_streaming_compliance.py` |
| `lint` | <60s | `ruff check` + `ruff format --check` (Python) |
| `typecheck` | <2min | `pyright --strict` |
| `test-unit` | <5min | `pytest tests/unit/` |
| `test-integration` | <5min | `pytest tests/integration/` |
| `frontend` | <3min | `check_frontend_file_size.py` + `biome check` + `validate-i18n` + `pnpm type-check` + `pnpm test` + `pnpm build` |
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
        entry: bash -c 'npx tsx scripts/validate-i18n.ts'
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

## INFRA-011 Stabilization Gate Commands

INFRA-011 adds ratcheted/no-growth checks for AI-feature stabilization:

| Command | Checker | Purpose |
|---------|---------|---------|
| `just check-adoption` | `scripts/check_adoption.py` | Validates feature adoption scores and ratchets prompt/adoption WARN debt against `scripts/architecture/ai-gate-baseline.json`. |
| `just check-exceptions` | `scripts/check_exception_baseline.py` | Prevents approved architecture exceptions from growing without ADR/user approval. |
| `just check-frontend-size` | `scripts/check_frontend_file_size.py` | Enforces/report-ratchets TypeScript/TSX RULE-04 file-size debt for touched frontend hubs. |
| `just check-streaming` | `scripts/check_streaming_compliance.py` | Ensures backend SSE-capable AI endpoints use frontend `connectSSE()` coverage. |
| `just check-prompts-strict` | `scripts/check_prompt_structure.py --strict` | Treats prompt structure warnings as CI-relevant failures after baseline classification. |

These gates are stabilization prerequisites for lifting the ADR-027 AI feature
freeze. Existing classified legacy debt may shrink; new WARNs, new exceptions,
or new frontend hard-limit violations require Architecture re-review and explicit
approval.

## Streaming Compliance Checker

`scripts/check_streaming_compliance.py` enforces **RULE-20** (no deferred streaming):

- Discovers all backend SSE endpoints (StreamingResponse routes)
- Checks that the frontend consumes them via `connectSSE()` (not REST calls)
- Reports violations where `apiClient` is used instead of `connectSSE`

### Usage

```bash
# Human-readable report
just check-streaming

# JSON output (for tooling)
uv run python scripts/check_streaming_compliance.py --json
```

### CI Integration

Runs as part of the INFRA-011 architecture gate set and is ratcheted against the
AI gate baseline. Existing classified gaps may be tracked while they shrink; new
streaming gaps fail stabilization review unless explicitly approved by
Architecture/user exception.

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
| **Database** | `db-migrate` | Run pending Alembic migrations (optional — runs automatically on startup) |
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

## Self-Hosted Deployment

Narrare ships as a single Docker image containing both the FastAPI backend and
the Next.js frontend. PostgreSQL (with pgvector) and Redis run alongside it
via Docker Compose.

### Release Artifacts

Each release produces:

| Artifact | Location | Description |
|----------|----------|-------------|
| Docker image | `ghcr.io/<owner>/narrare:<version>` | Single image with API + frontend |
| Release bundle | `narrare-<version>.zip` | docker-compose.yml + .env.example + SBOM + README |
| CycloneDX SBOM | Release asset `sbom.cyclonedx.json` | Machine-readable SBOM (via Syft) |
| Python deps | Release asset `requirements.txt` | Python dependencies exported from uv.lock |

The Docker image is **private** by default (inherits repository visibility).
End users authenticate once via `docker login ghcr.io`.

### Quick Start (End User)

```bash
# 1. Download and extract the release bundle
unzip narrare-0.2.0.zip
cd narrare-0.2.0/

# 2. Configure environment
cp .env.example .env
# Edit .env — set SECRET_KEY, NARRARE_ENCRYPTION_KEY, and AI provider keys

# 3. Start
docker compose up -d

# 4. Open http://localhost:3000
```

### Required Configuration

| Variable | Required | How to generate |
|----------|----------|-----------------|
| `SECRET_KEY` | Yes | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `NARRARE_ENCRYPTION_KEY` | Yes | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DATABASE_URL` | Yes | Must use `@postgres:5432/` (Docker service name, not localhost) |
| `REDIS_URL` | Yes | Must use `redis://redis:6379/0` (Docker service name) |
| AI API key | At least one | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc. |

### Updates

```bash
docker compose pull
docker compose up -d
# Migrations run automatically on startup — no manual step needed
```

### Architecture

The production image is a multi-stage Docker build:

```
┌──────────────────────────────────────┐
│  ghcr.io/<owner>/narrare:<version>   │
│                                      │
│  Port 3000 → Next.js (external)     │
│              ↓ /api/v1/* rewrite     │
│  Port 8000 → FastAPI (internal)     │
└──────────────────────────────────────┘
         │                │
    ┌────┘                └────┐
    ▼                         ▼
 PostgreSQL                Redis
 (pgvector)               (cache)
```

- **FastAPI** listens on `127.0.0.1:8000` (internal only)
- **Next.js** listens on `0.0.0.0:3000` (external) and proxies `/api/v1/*` to the backend
- Health check: `GET /health` on port 8000

### CI/CD: Release Pipeline

The `release-please.yml` workflow automates the entire release:

1. **Version detection** — release-please parses conventional commits
2. **GitHub Release** — created with auto-generated changelog
3. **Docker build** — multi-stage build, pushed to GHCR
4. **SBOM generation** — CycloneDX SBOM (via Syft) and Python requirements (via `uv export`)
5. **Release bundle** — zip with docker-compose.yml + .env.example + SBOM files + README
6. **Bundle + SBOM upload** — attached to the GitHub Release as separate assets

```
merge to main
  → release-please detects version bump
    → opens release PR
      → on merge: GitHub Release created
        → Docker image built + pushed to GHCR
        → Release bundle created + attached
```

## Environment Variables

See `.env.example` for all required variables:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://narrare:narrare@localhost:5432/narrare_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# Auth
SECRET_KEY=<generate with: just generate-secret>
# Must match SECRET_KEY (used by frontend proxy for JWT verification)
AUTH_JWT_SECRET=${SECRET_KEY}
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

# API Key Encryption (required for AI provider features)
NARRARE_ENCRYPTION_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# Default Model
DEFAULT_LLM_MODEL=anthropic/claude-sonnet-4-5
```

### NARRARE_ENCRYPTION_KEY

Required for AI provider features (multi-provider support, user API key storage).

| Property | Value |
|----------|-------|
| Required | Yes |
| Description | Fernet encryption key for encrypting user API keys at rest |
| Generate | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| Warning | **If this key is lost, all user API keys are unrecoverable.** Store securely and back up. |
| Rotation | To rotate: generate new key, decrypt all keys with old key, re-encrypt with new key, update env var |

The key is used by `core/shared/crypto.py` to encrypt API keys before storing them in the `user_providers` table and decrypt them only when constructing a provider instance for an LLM call. Keys are never logged or returned via API.

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

## Release Verification

Each release produces verifiable artifacts. The following sections document how
to verify the authenticity and integrity of a release.

### Release Bundle Integrity

The release bundle (`narrare-<version>.zip`) is published as a GitHub Release
artifact. All GitHub Release artifacts are automatically signed by GitHub's
infrastructure. To manually verify the download:

```bash
# Download and checksum
sha256sum narrare-<version>.zip
# Compare with the hash shown in the GitHub Release metadata
```

### Docker Image Verification

The Docker image is pushed to GHCR with both a version tag and a digest:

```bash
# Pull by version tag
docker pull ghcr.io/<owner>/narrare:<version>

# Pull by digest (immutable — recommended for production)
docker pull ghcr.io/<owner>/narrare@<digest>
```

Each release's GitHub Release summary includes the image digest.

### SBOM Verification

Two SBOM artifacts are published with each release:

| SBOM | Format | Tool | Content |
|------|--------|------|---------|
| `sbom.cyclonedx.json` | CycloneDX JSON | Syft | Full image SBOM (system + Python + Node.js) |
| `requirements.txt` | pip requirements.txt | uv export | Python dependencies only |

The SBOM is generated **during the release workflow** directly from the
published Docker image, ensuring it reflects exactly what is in the image.

You can scan the SBOM for vulnerabilities:

```bash
# Using Grype (from Anchore)
grype sbom:sbom.cyclonedx.json

# Using Trivy (from Aqua Security)
trivy sbom sbom.cyclonedx.json
```

### Cosign Signing (Future)

For cryptographic signing of Docker images, Cosign keyless signing via GitHub
OIDC is the planned approach:

- **Tool:** `sigstore/cosign-installer` (available as GitHub Action)
- **Key management:** Keyless mode — no manual key management needed
- **OIDC provider:** `https://token.actions.githubusercontent.com` (GitHub)
- **Identity:** The release workflow identity (repo + ref)

Implementation is deferred to a future milestone. See the release bundle README
for the planned verification command.

### Provenance Trust Model

| Artifact | Method | Trust |
|----------|--------|-------|
| GitHub Release | Signed by GitHub infrastructure | High |
| Docker image (by digest) | Cryptographically content-addressed | High |
| Release bundle | SHA256 checksum in metadata | Medium |
| CycloneDX SBOM | Generated from published image in trusted CI | Medium |
| Cosign signature | Public-key cryptography (future) | High |

## Monitoring

- Application logs: structlog with JSON output
- Metrics: Prometheus-compatible counters where services expose runtime metrics
- Tracing: OpenTelemetry + Langfuse for LLM observability

> Maintained by: Deployment Agent
