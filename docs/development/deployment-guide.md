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

The project uses `uv` with workspace members (`apps/api`, `packages/core`, `packages/i18n`). Two setup paths are available:

| Command | When to use | What it installs |
|---------|-------------|------------------|
| `just dev-setup` | Full-stack work including NLP/analysis features | Dev deps + `--extra nlp` + spaCy language models (~200 MB). ~10 min. |
| `just dev-setup-min` | Frontend, core, or agent work (no NLP) | Dev deps only (~200 MB smaller). ~5 min. Add NLP later with `just install-nlp-models`. |

Both recipes create `.env`, install pre-commit hooks, start Docker services,
run migrations, and seed the dev user.

Under the hood, the Python sync uses `uv` with the workspace members:

```bash
# Install dev dependencies, NLP extra, and workspace member packages
uv sync --frozen --all-packages --group dev --extra nlp

# Lightweight equivalent (no NLP extra)
uv sync --frozen --all-packages --group dev
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

### Setup Troubleshooting

#### `uv sync --frozen` fails with a lockfile error

**Symptom:** `just dev-setup` (or `uv sync --frozen --all-packages …` directly)
aborts with a message like *"the lockfile … needs to be updated"*,
*"lockfile out of date"*, or a hash/diff error.

**Cause:** `--frozen` is intentional — it enforces reproducible installs by
refusing to touch `uv.lock`. The error means the lockfile on your branch no
longer matches the dependencies declared in the `pyproject.toml` files. This
happens most often when:

- you checked out a branch where someone ran `just deps-update`,
  `uv add …`, or `uv remove …` and committed the `pyproject.toml` change
  **but** the `uv.lock` on your branch predates it;
- a Dependabot/renovate PR updated `pyproject.toml` without a matching lockfile;
- you are on `main` right after such a change landed.

**Fix — pick the one matching your situation:**

1. **You just want to run the project (most common):** fetch the committed
   lockfile that matches the branch.
   ```bash
   git checkout main -- uv.lock   # if the drift is on a feature branch
   uv sync --frozen --all-packages --group dev --extra nlp
   ```

2. **You intentionally changed dependencies and need to update the lockfile:**
   drop `--frozen` once to regenerate, then commit both files together.
   ```bash
   uv lock --upgrade-package <name>      # or: uv lock (whole graph)
   uv sync --all-packages --group dev --extra nlp   # no --frozen here
   git add pyproject.toml uv.lock && git commit
   ```
   Never commit a `pyproject.toml` dependency change without its `uv.lock`.

3. **You are reviewing a Dependabot PR:** the PR's CI will fail the same way
   until the lockfile is regenerated; this is the signal that the PR is
   incomplete. Regenerate locally (`uv lock`) and push.

**When `--frozen` may be dropped deliberately:** only on the machine that owns
the dependency change, to regenerate the lockfile. CI and `just dev-setup`
always keep `--frozen` — that is the contract that makes installs reproducible
across VM-first dev, DevContainer, and CI.

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

The CI workflow (`.github/workflows/ci.yml`) defines a 9-job pipeline with
staged execution. Job details are maintained in the workflow file; this table
is a quick orientation only and may lag behind the canonical source.

| Job | Purpose | Notes |
|-----|---------|-------|
| `architecture` | Architecture, prompt surface/structure, version drift, exception sync, configuration matrix, OpenAPI drift, invocation probes, adoption, locale, doc/registry/gate drift, governance, streaming, AI-interaction, system health, test-coverage gaps, eval-smoke (blocking), eval-drift (warning), SSOT-facts (warning) | Fail-fast root; downstream jobs depend on it |
| `lint` | `ruff check` + `ruff format --check` (Python) | Runs after `architecture` |
| `typecheck` | `pyright --strict` | Runs after `architecture` |
| `security` | `bandit -r` + `pip-audit` (with documented ignore-IDs) + `check_secrets.py`/Gitleaks | Runs after `architecture` |
| `test-unit` | `pytest tests/unit/` with global `--cov-fail-under=80`, then `check_module_coverage.py --fail` (RULE-10 module targets + ratcheted baselines) | Runs after lint/typecheck |
| `test-integration` | `pytest tests/integration/` against `pgvector/pgvector:pg17` and `redis:8-alpine` services | Runs after lint/typecheck |
| `update-coverage-badge` | Refreshes coverage badge | Non-blocking helper job |
| `frontend` | `check_frontend_file_size.py`, biome, i18n validation, `pnpm type-check`, `pnpm test`, component marker (`check-testid.ts`), `pnpm build`; test performance is warning-only (threshold 240s) | Runs after `architecture` |
| `test-e2e` | Full-stack end-to-end tests | Runs only on pushes to `main` |

A `warnings-summary` step aggregates non-blocking warnings from all jobs.

**Job ordering (simplified):**

```
architecture → lint + typecheck + security + frontend (parallel)
             → test-unit + test-integration (after lint/typecheck)
             → test-e2e (main branch only)
```

Tests run only if lint and typecheck pass (saves CI minutes).

**PR merge requires ALL applicable jobs green. No bypass.**

### Workflow: Eval Nightly (`.github/workflows/eval-nightly.yml`)

Scheduled runtime evaluations of the LLM features (separate from PR-CI).
Runs on a schedule and via `workflow_dispatch`; requires the
`NARRARE_EVAL_API_KEY` repository secret. Smoke-evals (secret-free) run in
PR-CI inside the `architecture` job; the nightly workflow covers the
real-provider runtime evaluations (LLM-as-judge, tone-of-voice, prose
quality). Runtime evals skip warning-only when the secret is unavailable
(relevant for forks).

### Workflow: Mutation Testing (`.github/workflows/mutation-testing-monthly.yml`)

Monthly mutation-testing run. Non-blocking; tracks test quality over time.

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

`scripts/check_architecture.py` enforces a set of RULE-XX constraints defined
in `docs/_shared/CONSTRAINTS.md`. For the authoritative list of enforced rules,
run the checker's self-report:

```bash
python scripts/check_architecture.py --list-rules
```

or see the `ENFORCED_RULES` constant in `scripts/check_architecture.py`.
Do not maintain a separate rule list in docs — it drifts.

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
| **Setup** | `dev-setup` | First-time setup: install dev + NLP deps/models, create .env, run migrations (~10 min) |
| | `dev-setup-min` | Lightweight setup: dev deps without NLP models (~200 MB smaller, ~5 min) |
| | `generate-secret` | Generate a secure `SECRET_KEY` |
| | `install-nlp-models` | Install spaCy language models (de, en, fr) |
| **Development** | `dev` | Start all services (API + frontend) |
| | `dev-api` | Start API server only (port 8000) |
| | `dev-frontend` | Start frontend only (port 3000) |
| | `dev-e2e` | Start API in E2E test mode (no real LLM calls) + frontend |
| | `dev-worker` | Start TaskIQ worker (Phase 5+) |
| | `dev-services` | Start Docker services (postgres + redis) |
| | `dev-services-stop` | Stop Docker services |
| **Database** | `db-migrate` | Run pending Alembic migrations (also runs automatically on startup) |
| | `db-revision "msg"` | Create a new migration (e.g. `just db-revision "add table"`) |
| | `db-status` | Show current migration status |
| | `db-history` | Show migration history |
| | `db-reset` | Reset dev database (DANGER: destroys all data) |
| | `db-shell` | Open psql shell |
| **Testing** | `test` | Run all tests (parallel) |
| | `test-unit` | Run unit tests only (fast, no Docker needed) |
| | `test-integration` | Run integration tests (requires Docker services) |
| | `test-e2e` | Run E2E tests (requires full stack) |
| | `test-frontend` | Run frontend tests (Vitest) |
| | `test-cov` | Run tests with coverage report |
| | `test-vrt` | Run Playwright VRT screenshot tests |
| **Quality (Python)** | `check` | Run all checks (architecture + lint + typecheck + security + frontend) |
| | `check-architecture` | Run architecture constraint checker |
| | `lint` | Run ruff linter with auto-fix |
| | `typecheck` | Run pyright type checker |
| | `security` | Run security checks |
| **Quality (Frontend)** | `check-frontend` | Run all frontend checks (lint + typecheck + test) |
| | `lint-frontend` | Run non-mutating frontend lint/format checks |
| | `format-frontend` | Run frontend formatter |
| | `typecheck-frontend` | Run TypeScript type checking on frontend |
| **Dependencies** | `deps` | Show dependency tree |
| | `deps-update` | Update all dependencies to latest compatible versions |
| **Release** | `changelog` | Preview changelog for unreleased changes |
| | `version` | Show current version |

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

### Rollback

Narrare does not run a separate rollback service: a rollback is an image
replacement combined with a conscious decision about the database schema. The
release pipeline produces immutable version tags and digests (see
[Docker Image Verification](#docker-image-verification)), so reverting to a
previous release is a two-step operation.

#### Step 1 — Pull and start the previous image

```bash
# Option A: revert by version tag (SemVer, e.g. 0.4.2)
docker compose pull
docker image tag ghcr.io/<owner>/narrare:0.4.2 ghcr.io/<owner>/narrare:latest
docker compose up -d

# Option B (recommended for production): revert by digest (immutable)
docker pull ghcr.io/<owner>/narrare@<previous-digest>
docker image tag ghcr.io/<owner>/narrare@<previous-digest> ghcr.io/<owner>/narrare:latest
docker compose up -d
```

`docker-compose.release.yml` pins the image as `narrare:latest`, so re-tagging
the target image to `:latest` and running `up -d` recreates the containers with
the older image. Each release's GitHub Release summary lists the image digest.

#### Step 2 — Decide on database migrations

On startup, `lifespan.py` runs `alembic upgrade head` automatically (see
[Updates](#updates)). This is the critical rollback constraint: **if the newer
release ran a migration that the older image does not know about, starting the
older image will either fail the startup health check or run against a schema it
was not built for.** Two cases:

- **Patch-level rollback (e.g. 0.4.2 → 0.4.1), no schema change between the
  releases:** no migration action needed. The older image starts cleanly.
- **Minor/major rollback across a schema migration:** you must downgrade the
  schema *before* starting the older image, while the newer image is still
  running or via a one-off migration container:

  ```bash
  # Find the revision the older image expects (it is the latest migration
  # file present in that image's apps/api/alembic/versions/)
  docker compose run --rm --no-deps narrare \
      alembic downgrade <target-revision>

  # Then start the older image (see Step 1)
  ```

  All Narrare migrations ship with a `downgrade()` path, but **`downgrade()` only
  reverses schema, not data**. If the newer release ran a data migration (e.g.
  backfilled a column, dropped a now-unused column, or transformed rows), that
  data is **not recoverable** by rolling back — treat such releases as
  forward-only. Review the migration files between the two releases before
  attempting a downgrade, and **back up the database first**:

  ```bash
  docker compose exec postgres pg_dump -U narrare narrare > backup-$(date +%F).sql
  ```

#### Scenario: rollback one minor version

Rolling back from `0.5.0` to `0.4.2`:

1. Back up the database (`pg_dump` command above).
2. Check the migration files added between `0.4.2` and `0.5.0` — if any are
   data migrations or destructive (`drop_table` / `drop_column` on live data),
   stop here: the rollback is **forward-only** and you must fix forward instead.
3. If only schema-additive migrations exist, downgrade the database to the
   revision that ships with `0.4.2` (see Step 2).
4. Pull and tag the `0.4.2` image (Step 1, Option B with the digest preferred).
5. `docker compose up -d` and verify `GET /health` returns `healthy` (or
   `degraded` with an OTel-only cause — see
   [Health Endpoint](#monitoring)).

#### Caveats

- **`latest` tag moves forward only.** Reverting via tag requires pinning to the
  explicit old tag or digest as shown above; `docker compose pull` alone always
  pulls the newest `latest`. Use digest-based pinning for production rollbacks.
- **Stateful services (Postgres, Redis) are on named volumes** and are not
  touched by an image rollback. If the newer release changed the Postgres major
  version, a rollback may require a separate `pg_dump`/`restore` — that scenario
  is not covered by a simple image replacement.
- **Workers (`taskiq`) also pin to `latest`** in `docker-compose.release.yml`.
  The rollback procedure above re-tags a single image used by both the API and
  worker services, so both revert together.

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

## CI Environment Notes

### PostgreSQL "root" Role Connection Errors (GitHub Actions)

When running CI workflows with PostgreSQL service containers (e.g., `pgvector/pgvector:pg17`),
the CI log may show periodic `FATAL: role "root" does not exist` errors every 5 seconds
throughout the job duration.

**Root cause:** This is infrastructure-level behavior from the GitHub Actions runner / Docker
daemon checking service container connectivity. The system probes PostgreSQL with a default
`root` user — not `narrare` as configured in the workflow's `POSTGRES_USER` env var.

**Impact:** None. These are authentication failures at the Docker network level, not from
any application code. Our services always use `narrare:narrare@localhost:5432/narrare_test`
(via `DATABASE_URL` env var). The errors are innocuous noise.

**Not fixable from application code.** If the noise is problematic, consider adding
`client_min_messages=error` to the Postgres container's startup, or suppressing the warnings
in the CI log viewer via log filters.

> Maintained by: Deployment Agent
