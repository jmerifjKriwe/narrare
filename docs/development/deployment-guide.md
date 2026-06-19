# Deployment Guide — Narrare

> **Deployment and development environment configuration.**
> Location: `docs/development/deployment-guide.md`

## Dev Environment

### Prerequisites

- Docker and Docker Compose v2.24+ (required for release compose validation without a committed `.env`)
- Python 3.14+
- Node.js 24+
- pnpm 11.5.2 via the root `package.json` `packageManager` pin
- just (command runner)

Canonical runtime and package-manager versions live in
`docs/_shared/TECH_STACK.md` and root `package.json`; keep this guide focused on
how to operate the environments.

### Python Environment Setup

The project uses `uv` with workspace members (`apps/api`, `packages/core`, `packages/i18n`). To set up the Python environment:

```bash
# Install dev dependencies, NLP extra, and workspace member packages
uv sync --frozen --all-packages --group dev --extra nlp
```

**Important:** `uv sync` alone does NOT install workspace member packages (narrare, narrare_core) in editable mode. You MUST use `--all-packages` to make workspace members importable. Without this:
- Pre-commit hooks fail (OpenAPI spec regeneration: `No module named 'narrare'`)
- Pyright reports thousands of unresolved imports
- Running `uv run python` cannot import `narrare` or `narrare_core`

The setup contract also includes `--group dev` for developer tools and
`--extra nlp` because `just install-nlp-models` intentionally assumes spaCy is
already installed from the core package's optional NLP extra.

**Verification:**

```bash
uv run python -c "import narrare_core; import narrare; import spacy; print('OK')"
```

### Local Services

VM-first development is the primary setup mode. Run `just` commands on the VM or
host unless a command explicitly says it is for the DevContainer. Host-side
database and Redis helpers target published `localhost` ports; container-mode
helpers use Docker service names.

```bash
# Validate the VM-first development Compose topology
docker compose -f docker-compose.dev.yml config

# Start all services (postgres+pgvector, redis)
just dev-services

# Stop services
just dev-services-stop

# View logs
just logs
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

DevContainer support is optional. It must stay portable and must not become a
requirement for VM-first development.

The `.devcontainer/` configuration provides:
- Python 3.14 with all dependencies
- Node.js 24+ for frontend
- Pre-configured extensions
- Automatic service startup

Validate the merged DevContainer topology explicitly from the repository root:

```bash
docker compose -f docker-compose.dev.yml -f .devcontainer/docker-compose.devcontainer.yml config
```

## CI/CD Pipelines

### Workflow: CI (`.github/workflows/ci.yml`)

CI is the single blocking owner for setup, architecture, and application quality
gates. It runs on pushes to protected branches and on PRs that touch application,
docs, setup, Docker/Compose, workflow, lockfile, package-manager, and pre-commit
paths; see `.github/workflows/ci.yml` for the canonical path filter.

It covers:
1. Linting (ruff, biome)
2. Architecture checks (`check_architecture.py`)
3. Unit tests
4. Integration tests
5. Build verification
6. Setup/config drift checks, including locale and documentation drift checks

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

7-job pipeline with staged execution. Job details are maintained in
`.github/workflows/ci.yml`; this table is a quick orientation only.

| Job | Target | Commands |
|-----|--------|----------|
| `architecture-check` | <30s | `python scripts/check_architecture.py` + `check_exception_baseline.py` + `check_adoption.py` + `check_prompt_structure.py` + `check_streaming_compliance.py` |
| `lint` | <60s | `ruff check` + `ruff format --check` (Python) |
| `typecheck` | <2min | `pyright --strict` |
| `test-unit` | <5min | `pytest tests/unit/` |
| `test-integration` | <5min | `pytest tests/integration/` |
| `frontend` | <3min | `check_frontend_file_size.py` + non-mutating frontend lint/format checks + i18n validation + `pnpm type-check` + `pnpm test` + `pnpm build` |
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
just hooks-update

# Run manually
pre-commit run --all-files
```

Hooks are configured in `.pre-commit-config.yaml`; that file is the canonical
source for exact hook commands and stages. Important behavior:

- Architecture, prompt, adoption, OpenAPI, Python, frontend, i18n, TypeScript,
  security, hygiene, and commit-message checks run locally where applicable.
- Some hooks intentionally mutate files (`openapi-regenerate`, `ruff-lint`,
  `ruff-format`, `biome-frontend`, file hygiene fixers).
- Type checks are full-project checks where the hook declares `pass_filenames:
  false`; do not describe them as changed-file-only checks unless the config says
  so.
- CI remains the blocking gate; pre-commit is local fast feedback.

Current hook groups:

| Hook | Stage | Command |
|------|-------|---------|
| Architecture/setup | pre-commit | Constraint, prompt structure, adoption score, and OpenAPI drift checks |
| Python quality | pre-commit | Ruff lint/format, pyright, bandit |
| Frontend quality | pre-commit | Biome, i18n validation, TypeScript type check |
| File hygiene | pre-commit | Whitespace, EOF, YAML/TOML/JSON, merge-conflict, large-file checks |
| Commit message | commit-msg | Conventional commit validation |

### Fast-Path for Quick Iterations

The full pre-commit suite runs architecture, prompt, adoption, pyright,
TypeScript, Biome, and bandit checks on every commit. That is intentional —
it catches regressions early. During rapid local iteration, however, the full
gate can slow you down.

**Fast-path option — skip heavy hooks:**

```bash
SKIP=pyright,architecture-constraints,adoption-score,prompt-structure git commit -m "feat(core): …"
```

This skips the four slowest hooks (type checker, architecture constraints,
adoption score, prompt structure) while keeping lint, format, file hygiene,
and commit-message checks active.

**Rules for using the fast-path:**

1. **CI is the authoritative gate.** The full check suite runs in CI on every
   push and PR. Fast-path commits still get validated.
2. **Run `just check` before pushing.** After using the fast-path, you **must**
   run the complete check locally (or verify CI is green) before pushing:
   ```bash
   just check            # architecture + lint + typecheck + security
   just check-frontend   # frontend lint + format + type + test
   ```
3. **Never push without validation.** Pushing fast-path commits without
   running the full checks locally or confirming CI green is a violation.
4. **Merge requests require all CI jobs green regardless.** No bypass.

**Why this exists:** Local iteration speed matters. CI remains the
non-negotiable quality gate — the fast-path is a convenience, not an
exemption.

> **Cross-reference:** See also `docs/development/coding-standards.md`
> (Git Commit Convention) and `docs/development/testing-standards.md`
> (Fast Developer Feedback).

## Architecture Checker

`scripts/check_architecture.py` enforces:
- RULE-01b: LLM imports
- RULE-02: Prompt building
- RULE-04: File size limits
- RULE-06: Router purity
- RULE-11: Silent failures

## INFRA-011 Stabilization Gate Commands

INFRA-011 adds ratcheted/no-growth checks for AI-feature stabilization:

| Command | Checker | Purpose |
|---------|---------|---------|
| `just check-adoption` | `scripts/check_adoption.py` | Validates static + runtime adoption, requires correlated evidence for ADR-045 PASS, and ratchets prompt/adoption debt against `scripts/architecture/ai-gate-baseline.json`. |
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
| **Setup** | `dev-setup` | First-time setup: install dev + NLP deps/models, create .env, run migrations |
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
| | `check-frontend` | Run non-mutating frontend file-size, lint/format, type, and test checks |
| | `lint` | Run ruff lint + fix |
| | `format` | Run ruff format |
| | `typecheck` | Run pyright |
| **Release** | `changelog` | Preview changelog for unreleased changes |

## Release Process

1. All commits follow conventional format
2. Merge to main triggers the release workflow
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
| Docker image | `ghcr.io/<owner>/narrare:<version>` | Single image with API + frontend. The release workflow derives `<owner>` from the repository owner in lowercase; release compose defaults to the same image tuple. |
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

# 3. Start from the release bundle
docker compose up -d

# 4. Open http://localhost:3000
```

### Required Configuration

| Variable | Required | How to generate |
|----------|----------|-----------------|
| `SECRET_KEY` | Yes | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `NARRARE_ENCRYPTION_KEY` | Yes | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DATABASE_URL` | Yes | For release compose, use `@postgres:5432/` (Docker service name, not localhost) |
| `REDIS_URL` | Yes | For release compose, use `redis://redis:6379/0` (Docker service name) |
| AI API key | At least one | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc. |

### Compose Configuration Validation

The repository has no default `docker-compose.yml`; every validation command must
name the target topology explicitly.

```bash
# VM-first development services
docker compose -f docker-compose.dev.yml config

# Optional DevContainer overlay merged with development services
docker compose -f docker-compose.dev.yml -f .devcontainer/docker-compose.devcontainer.yml config

# Self-hosted release topology; config validation does not require a real .env
docker compose -f docker-compose.release.yml config
```

Release compose treats `.env` as optional for `config` validation only. Actual
self-hosted deployment still requires copying `.env.example` to `.env` and
configuring `SECRET_KEY`, `NARRARE_ENCRYPTION_KEY`, Docker service URLs, and at
least one AI provider key before `docker compose up -d`. The repository
`.env.example` is the VM-first template; release deployments must switch service
URLs to Docker service names as shown in `docker-compose.release.yml`.

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

The release workflow (`.github/workflows/release-please.yml`) automates the release:

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
        → Docker image built + pushed to GHCR as ghcr.io/<owner>/narrare
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

# Observability (optional; OpenTelemetry-only, ADR-031)
OTEL_EXPORTER_OTLP_ENDPOINT=
OTEL_SERVICE_NAME=narrare-api
# Include prompt/completion content in Pydantic-AI spans.
# Defaults to true outside production and false when ENVIRONMENT=production.
NARRARE_OTEL_INCLUDE_CONTENT=

# CSRF protection — trusted origins for Origin/Referer validation
# Comma-separated list; default: http://localhost:3000
NARRARE_CSRF_TRUSTED_ORIGINS=http://localhost:3000
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

### NARRARE_CSRF_TRUSTED_ORIGINS

Configures trusted origins for the CSRF defense-in-depth Origin/Referer validation
middleware. Requests from non-trusted origins receive HTTP 403.

| Property | Value |
|----------|-------|
| Required | No |
| Default | `http://localhost:3000` |
| Description | Comma-separated list of allowed origins for state-changing requests (POST/PUT/PATCH/DELETE). Bearer-authenticated requests without Origin are exempt (programmatic clients). |
| Production | Set to your deployed origin, e.g. `https://narrare.example.com` |
| WebSocket | Same origin list used for WebSocket handshake validation (close code 4001 on mismatch) |

Implemented by `OriginValidationMiddleware` in `apps/api/narrare/_app/middleware.py`
per AUFG-05-13.

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
- Tracing: OpenTelemetry-only trace standard for API and Pydantic-AI LLM/agent/tool spans (ADR-031)
- Langfuse is removed from the core runtime; Logfire is not used for core observability
- Production should leave `NARRARE_OTEL_INCLUDE_CONTENT=false` unless prompt/completion capture is explicitly approved

> Maintained by: Deployment Agent
