# Narrare — Task Runner
# Requires: just (https://just.systems)
# Usage: just <command>

# NOTE: no ``set dotenv-load`` here. The root ``.env`` is read by the API via
# pydantic-settings ``env_file`` (apps/api/narrare/_app/settings_model.py) and by
# scripts via ``Settings()`` — loading it into every recipe's environment
# created a double source of truth (env var vs. env_file) and contaminated
# hermetic test runs. See audit in PR / commit message.
set shell := ["bash", "-euo", "pipefail", "-c"]

# Default: list all commands
default:
    @just --list

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Check if docker is available (skip in explicit container mode where services already run)
[private]
_ensure-services:
    @if [ "${NARRARE_DEV_MODE:-host}" = "container" ]; then \
        echo "ℹ️  Container mode — assuming Compose services already running"; \
    elif command -v docker >/dev/null 2>&1; then \
        docker compose -f docker-compose.dev.yml up -d --wait 2>/dev/null; \
    else \
        echo "ℹ️  Docker not available — assuming services already running (dev container?)"; \
    fi

# Stop Docker services (no-op if docker unavailable)
[private]
_stop-services:
    @if command -v docker >/dev/null 2>&1; then \
        docker compose -f docker-compose.dev.yml down; \
    else \
        echo "ℹ️  Docker not available — nothing to stop"; \
    fi

# Run SQL via psql directly in explicit host/container mode, with Docker fallback.
[private]
_psql-sql db sql:
    @mode="${NARRARE_DEV_MODE:-host}"; \
    if command -v psql >/dev/null 2>&1; then \
        if [ "$$mode" = "container" ]; then \
            PGPASSWORD=narrare psql -U narrare -h postgres -p 5432 -d {{db}} -c "{{sql}}"; \
        else \
            port=5432; [ "{{db}}" = "narrare_test" ] && port=5433; \
            PGPASSWORD=narrare psql -U narrare -h localhost -p "$$port" -d {{db}} -c "{{sql}}"; \
        fi; \
    elif command -v docker >/dev/null 2>&1; then \
        docker compose -f docker-compose.dev.yml exec postgres psql -U narrare -d {{db}} -c "{{sql}}"; \
    else \
        echo "❌ Neither psql nor docker available — cannot run SQL"; exit 1; \
    fi

# Drop and recreate a database (connects to maintenance DB)
[private]
_psql-recreate-db db:
    @mode="${NARRARE_DEV_MODE:-host}"; \
    if command -v psql >/dev/null 2>&1; then \
        if [ "$$mode" = "container" ]; then \
            PGPASSWORD=narrare psql -U narrare -h postgres -p 5432 -d postgres -c "DROP DATABASE IF EXISTS {{db}};" && \
            PGPASSWORD=narrare psql -U narrare -h postgres -p 5432 -d postgres -c "CREATE DATABASE {{db}};"; \
        else \
            PGPASSWORD=narrare psql -U narrare -h localhost -p 5432 -d postgres -c "DROP DATABASE IF EXISTS {{db}};" && \
            PGPASSWORD=narrare psql -U narrare -h localhost -p 5432 -d postgres -c "CREATE DATABASE {{db}};"; \
        fi; \
    elif command -v docker >/dev/null 2>&1; then \
        docker compose -f docker-compose.dev.yml exec postgres psql -U narrare -d postgres -c "DROP DATABASE IF EXISTS {{db}};" && \
        docker compose -f docker-compose.dev.yml exec postgres psql -U narrare -d postgres -c "CREATE DATABASE {{db}};"; \
    else \
        echo "❌ Neither psql nor docker available — cannot run SQL"; exit 1; \
    fi

# Open psql shell via psql directly in explicit host/container mode, with Docker fallback.
[private]
_psql-shell db:
    @mode="${NARRARE_DEV_MODE:-host}"; \
    if command -v psql >/dev/null 2>&1; then \
        if [ "$$mode" = "container" ]; then \
            PGPASSWORD=narrare psql -U narrare -h postgres -p 5432 -d {{db}}; \
        else \
            port=5432; [ "{{db}}" = "narrare_test" ] && port=5433; \
            PGPASSWORD=narrare psql -U narrare -h localhost -p "$$port" -d {{db}}; \
        fi; \
    elif command -v docker >/dev/null 2>&1; then \
        docker compose -f docker-compose.dev.yml exec postgres psql -U narrare -d {{db}}; \
    else \
        echo "❌ Neither psql nor docker available — cannot open shell"; exit 1; \
    fi

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

# First-time setup: install all dev + NLP dependencies, create .env, run migrations
# NOTE: existing devs (pre-2026-08-13) must re-run `just dev-setup-min`
# or `pre-commit install --hook-type pre-push` once to activate the
# pre-push stage. New clones get it automatically.
dev-setup:
    @echo "🚀 Setting up Narrare..."
    @if [ ! -f .env ]; then cp .env.example .env && echo "📋 Created .env — add your API keys"; fi
    uv sync --frozen --all-packages --group dev --extra nlp
    just install-nlp-models
    pre-commit install --install-hooks --hook-type pre-commit --hook-type pre-push
    pnpm install
    @echo "⏳ Starting services..."
    just _ensure-services
    just db-migrate
    uv run python scripts/seed_dev_user.py
    @echo "✅ Ready! Run 'just dev' to start."

# Lightweight setup: dev deps without NLP models (~200 MB smaller). Use for frontend/core work.
# NOTE: existing devs (pre-2026-08-13) must re-run `just dev-setup-min`
# or `pre-commit install --hook-type pre-push` once to activate the
# pre-push stage. New clones get it automatically.
dev-setup-min:
    @echo "🚀 Setting up Narrare (lightweight — no NLP models)..."
    @if [ ! -f .env ]; then cp .env.example .env && echo "📋 Created .env — add your API keys"; fi
    uv sync --frozen --all-packages --group dev
    pre-commit install --install-hooks --hook-type pre-commit --hook-type pre-push
    pnpm install
    @echo "⏳ Starting services..."
    just _ensure-services
    just db-migrate
    uv run python scripts/seed_dev_user.py
    @echo "✅ Ready! Run 'just dev' to start."
    @echo "ℹ️  NLP features (analysis) require: just install-nlp-models"

# Generate a secure secret key
generate-secret:
    uv run python -c "import secrets; print(secrets.token_hex(32))"

# ---------------------------------------------------------------------------
# NLP Models
# ---------------------------------------------------------------------------

# Print the download URL for a spaCy model (debugging helper)
# Usage: just _nlp-model-url de_core_news_md 3.8.0
[private]
_nlp-model-url model version:
    echo "https://github.com/explosion/spacy-models/releases/download/{{model}}-{{version}}/{{model}}-{{version}}-py3-none-any.whl"

# Install all spaCy language models (de, en, fr — medium)
install-nlp-models:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! uv run python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('spacy') else 1)" >/dev/null; then
        echo "❌ spaCy is not installed. Run 'uv sync --frozen --all-packages --group dev --extra nlp' before 'just install-nlp-models'." >&2
        exit 1
    fi
    if ! SPACY_VER=$(uv run python -c "import spacy; print(spacy.__version__.rsplit('.', 1)[0] + '.0')"); then
        exit 1
    fi
    echo "Installing spaCy models for version ${SPACY_VER}..."
    BASE="https://github.com/explosion/spacy-models/releases/download"
    uv pip install \
        "${BASE}/de_core_news_md-${SPACY_VER}/de_core_news_md-${SPACY_VER}-py3-none-any.whl" \
        "${BASE}/en_core_web_md-${SPACY_VER}/en_core_web_md-${SPACY_VER}-py3-none-any.whl" \
        "${BASE}/fr_core_news_md-${SPACY_VER}/fr_core_news_md-${SPACY_VER}-py3-none-any.whl"

# ---------------------------------------------------------------------------
# Development servers
# ---------------------------------------------------------------------------

# Start API in E2E test mode (no real LLM calls) + frontend
dev-e2e:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Starting all services in E2E TEST MODE (no real LLM calls)..."
    just _ensure-services

    mkdir -p logs
    > logs/dev.log

    cleanup() {
        echo ""
        echo "⏹  Shutting down..."
        for pid in $(jobs -p); do
            kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
        done
        wait 2>/dev/null || true
        echo "⏹  Stopped."
        exit 0
    }
    trap cleanup INT TERM

    NARRARE_E2E_TEST=1 just dev-api &
    just dev-frontend &
    wait

# Start all services (API + frontend)
dev:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Starting all services..."
    just _ensure-services

    # Ensure logs directory exists and truncate logfile
    mkdir -p logs
    > logs/dev.log

    cleanup() {
        echo ""
        echo "⏹  Shutting down..."
        for pid in $(jobs -p); do
            kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
        done
        wait 2>/dev/null || true
        echo "⏹  Stopped."
        exit 0
    }
    trap cleanup INT TERM

    just dev-api &
    just dev-frontend &
    wait

# Start API server only (port 8000)
dev-api:
    cd apps/api && uv run uvicorn narrare._app.main:app \
        --reload \
        --host 0.0.0.0 \
        --port 8000 \
        --log-level debug

# Start frontend only (port 3000)
dev-frontend:
    #!/usr/bin/env bash
    [ ! -f packages/web/.env.local ] && cp packages/web/.env.local.example packages/web/.env.local
    cd packages/web && pnpm dev

# Start Docker services (postgres)
dev-services:
    just _ensure-services

# Stop Docker services
dev-services-stop:
    just _stop-services

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# Run pending Alembic migrations
db-migrate:
    cd apps/api && uv run alembic upgrade head

# Create a new migration
# Usage: just db-revision "add user preferences table"
db-revision msg:
    cd apps/api && uv run alembic revision --autogenerate -m "{{msg}}"

# Show current migration status
db-status:
    cd apps/api && uv run alembic current

# Show migration history
db-history:
    cd apps/api && uv run alembic history --verbose

# Reset dev database (DANGER: destroys all data)
db-reset:
    @echo "⚠️  This will destroy all data in narrare_dev. Press Ctrl+C to cancel."
    @sleep 3
    just _psql-recreate-db narrare_dev
    just db-migrate
    uv run python scripts/seed_dev_user.py

# Open psql shell
db-shell:
    just _psql-shell narrare_dev

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

# Shared RAM-aware xdist worker selection (Q-019 OOM mitigation).
# Echoes "2" when RAM < 12 GB threshold, "auto" otherwise. Used by the
# `test` and `test-unit` recipes so both share the same guard.
# NOTE: detection measures AVAILABLE RAM on Linux (/proc/meminfo) but
# TOTAL RAM on macOS (sysctl hw.memsize) — macOS lacks a portable
# "available" metric; total is an overestimate there.
# See docs/architecture/questions/resolved/Q-019-xdist-worker-crash-oom.md.
[private]
_xdist-workers:
    #!/usr/bin/env bash
    set -euo pipefail
    # Detect RAM (MB). Linux: /proc/meminfo (available). macOS: sysctl (total).
    if [ -f /proc/meminfo ]; then
        avail_mb=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
    elif command -v sysctl >/dev/null 2>&1; then
        avail_mb=$(( $(sysctl -n hw.memsize) / 1048576 ))
    else
        avail_mb=0
    fi
    # RULE-18: 12288 MB = 12 GB threshold (Q-019 measured ~2.4 GB/worker headroom
    # on 9.6 GB / 4 workers; 12 GB gives ~3 GB/worker with -n auto on 4 cores).
    _RAM_THRESHOLD_MB=12288
    if [ "$avail_mb" -gt 0 ] && [ "$avail_mb" -lt "$_RAM_THRESHOLD_MB" ]; then
        echo 2
    else
        echo auto
    fi

# Run all tests. Worker count is RAM-aware via `_xdist-workers`: < 12 GB
# available → -n 2 (Q-019 OOM mitigation); otherwise -n auto. CI runs pytest
# directly (not this recipe) and is unaffected.
# See docs/architecture/questions/resolved/Q-019-xdist-worker-crash-oom.md.
test:
    #!/usr/bin/env bash
    set -euo pipefail
    workers=$(just _xdist-workers)
    uv run --all-packages pytest tests/ -v -n "$workers" -m "not schema_mutating"
    uv run --all-packages pytest tests/integration/ -v -m schema_mutating

# Run all tests with forced `-n 2` (explicit override; rarely needed now).
# The default `just test` is RAM-aware: it auto-selects `-n 2` on machines with
# < 12 GB available RAM and `-n auto` otherwise. Use this recipe only to force
# `-n 2` regardless of RAM detection (e.g., a large machine where you still want
# reduced parallelism, or if detection misfires).
# See docs/architecture/questions/resolved/Q-019-xdist-worker-crash-oom.md.
test-lowmem:
    uv run --all-packages pytest tests/ -v -n 2 -m "not schema_mutating"
    uv run --all-packages pytest tests/integration/ -v -m schema_mutating

# Run unit tests only (fast, no Docker needed). Parallelism is RAM-aware via
# `_xdist-workers` — same guard as `just test` (Q-019: `-n auto` on < 12 GB
# machines can OOM-kill a worker).
test-unit:
    #!/usr/bin/env bash
    set -euo pipefail
    workers=$(just _xdist-workers)
    uv run --all-packages pytest tests/unit/ -v -n "$workers" --dist loadfile

# Run tests single-threaded for debugging (disables the `randomly` plugin).
# NOTE: the name means "single-threaded", NOT "single file" — use `test-file` for scoped files.
test-single file="tests/":
    uv run --all-packages pytest {{file}} -v -p no:randomly

# Run integration tests (requires Docker services)
test-integration:
    just _ensure-services
    uv run --all-packages pytest tests/integration/ -v

# Run with coverage report
test-cov:
    uv run --all-packages pytest tests/ --cov --cov-report=term-missing --cov-report=html
    @echo "Coverage report: htmlcov/index.html"

# Run unit tests with coverage report
test-unit-cov:
    uv run --all-packages pytest tests/unit/ --cov --cov-report=term-missing
    @echo "Unit coverage complete."

# Run one or more specific test files. Everything after the recipe name is
# passed through to pytest, so extra flags work directly:
#   just test-file tests/unit/core/llm/test_gateway.py
#   just test-file tests/unit/core/llm/test_gateway.py -x -p no:xdist
#   just test-file tests/unit/core/llm/test_gateway.py --pdb -k "session"
# (Plain pytest runs single-process: xdist `-n` only comes from the `test`/
# `test-unit` recipes (RAM-aware: `-n 2` or `-n auto`), so `-p no:xdist`
# is optional here.)
test-file +files:
    uv run --all-packages pytest {{files}} -v

# Run tests matching a pattern
# Usage: just test-match "test_gateway"
test-match pattern:
    uv run --all-packages pytest tests/ -v -k "{{pattern}}"

# Run E2E tests directly against an already-running stack (60s per-test timeout).
# For the CI-faithful wrapper (starts services, ENVIRONMENT=test, --timeout=300),
# prefer:  just e2e
test-e2e:
    uv run --all-packages pytest tests/e2e/ -v -m e2e --timeout=60

# Run E2E tests against full stack — CI-faithful (starts API+frontend with ENVIRONMENT=test, narrare_test DB on :5433, --timeout=300; cleans up on exit). Requires: docker compose -f docker-compose.dev.yml up -d postgres_test. Frontend mode override: E2E_FRONTEND_MODE=build just e2e. See scripts/run_e2e.sh, .github/workflows/ci.yml (test-e2e job), tests/AGENTS.md.
e2e:
    bash scripts/run_e2e.sh

# Run frontend tests (Vitest)
test-frontend:
    cd packages/web && pnpm test

# Run frontend tests with coverage (fails if thresholds not met)
test-frontend-coverage:
    cd packages/web && pnpm test:coverage

# Run Playwright VRT screenshot tests (frontend only; preflight: deps + free :3000).
vrt:
    bash scripts/run_vrt.sh

# Regenerate VRT baselines (--update-snapshots) — review the diff before committing.
vrt-update:
    bash scripts/run_vrt.sh --update

# Regenerate Golden-Pages export baselines (sha256 + drift metrics) from the
# current narrare-roman / Typst / pandoc output. Review the git diff and commit
# only if the rendering change is intentional (ADR-081 §"Quality gate"). Mirrors
# the VRT baseline workflow: drift = CI failure → human review → bless.
golden-update:
    uv run pytest tests/golden/export/test_golden_pages.py -v -m golden_pages --golden-update -p no:xdist

# Back-compat alias for `just vrt`. Implemented as a wrapper recipe (not a just
# `alias`) because check_doc_drift.py --governance-only validates just commands
# against the recipe set and aliases are not visible to it.
test-vrt:
    just vrt

# Run all tests (backend + frontend)
test-all: test test-frontend

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

# WHY `uv run --all-packages` in gate recipes: the repo root is a virtual uv
# workspace (package = false), so a plain `uv run` only syncs the root
# dev-group closure — workspace-member dependencies (e.g. pyjwt, pinned in
# apps/api/pyproject.toml) can silently stay stale in the venv, and the local
# gate then audits outdated deps (false green). `--all-packages` makes every
# gate run guarantee the CI-equivalent closure (CI: one explicit
# `uv sync --frozen --all-packages --group dev`, then `uv run --no-sync`), so
# the venv self-heals after manual `uv lock` changes. Non-gate recipes (dev
# servers, db-*, setup, clean, shell, golden-update) keep plain `uv run`.

# Run all checks with compact summary (architecture + lint + typecheck + security + frontend)
check:
    uv run --all-packages python scripts/run_checks.py

# Run all checks with full tool output
check-verbose:
    uv run --all-packages python scripts/run_checks.py --verbose

# Full local gate after every slice/step: all checks (`check`) + full test
# suite (backend + frontend). `check` must stay in the gate — some of its
# scripts (check_empty_kb_vars, check_model_registry) have no pre-commit hook
# or CI job, so `just verify` is their only routine channel.
# `verify-quick` (below) is the fast variant: unit + frontend tests only.
verify: check test-all

# Quick validation: unit tests + frontend tests (no integration, no Docker,
# no `check`). Use for fast iteration between slices. Full gate is `just verify`.
verify-quick: test-unit test-frontend

# Scoped slice gate for one change set. NOT a substitute for `just verify`:
# it runs only the given paths and adds the scoped frontend check when a path
# is under packages/web/.
# Every path is normalised once before routing — a leading `./` is stripped and
# an absolute path under the repository root is made repo-relative — so each arm
# matches one canonical form and no arm can miss a variant of its own kind. A
# path that cannot be normalised to a repo-relative form aborts the recipe with
# a message instead of being handed to a tool that cannot parse it.
# Python paths: ruff (`lint-file`) → pyright with the correct config
# (`typecheck-file`), then pytest (`test-file`) only for paths under tests/ —
# pytest exits 5 on a source module because it collects no tests.
# Frontend paths skip the Python tools (ruff/pyright cannot parse TypeScript)
# and run scoped Biome instead. A slice may mix both kinds.
# Tests run only for the `tests/` paths the caller names: a source-only slice
# runs no tests at all, and naming e.g. `tests/integration/…` or `tests/e2e/…`
# sends that path to plain pytest (`test-file`: no `-m e2e` selection, no
# service/container boot) — the recipe provisions nothing beyond what is named.
# Usage: just verify-slice packages/core/narrare_core/llm/model_listing.py
#        just verify-slice ./tests/unit/core/llm/test_gateway.py packages/web/lib/providers.ts
verify-slice +paths:
    #!/usr/bin/env bash
    set -euo pipefail
    root="$PWD"
    py=()
    tests=()
    web=()
    for p in {{paths}}; do
        case "$p" in
            ./*) p="${p#./}"; [ -n "$p" ] || p="." ;;
            "$root") p="." ;;
            "$root"/*) p="${p#"$root"/}" ;;
            /*)
                echo "verify-slice: cannot route '$p' — absolute and outside" \
                    "the repository root ($root)" >&2
                exit 2
                ;;
        esac
        case "$p" in
            packages/web|packages/web/) web+=(".") ;;
            packages/web/*) web+=("${p#packages/web/}") ;;
            tests|tests/*) py+=("$p"); tests+=("$p") ;;
            *) py+=("$p") ;;
        esac
    done
    if [ "${#py[@]}" -gt 0 ]; then
        just lint-file "${py[@]}"
        just typecheck-file "${py[@]}"
    fi
    if [ "${#tests[@]}" -gt 0 ]; then
        just test-file "${tests[@]}"
    fi
    if [ "${#web[@]}" -gt 0 ]; then
        cd packages/web && npx biome check "${web[@]}"
    fi

# Scaffold the declaration surfaces of a new feature. Generates only artifacts
# that are green on arrival — never service/router/repository/component stubs
# (RULE-20). Layers: core, api, web. Optional: --with-intent NAME.
# Usage: just new-feature FIND-099 core api web
new-feature id +layers:
    uv run --all-packages python scripts/scaffold_feature.py {{id}} {{layers}}

# Run architecture constraint checker — THE architecture surface. `just check`
# does not restate this list: `scripts/_check_steps.py` runs this recipe, so a
# new architecture check is added here once. (T8b review F2: the two lists had
# already drifted — `generate_provider_catalog.py --check` was here and in CI
# but not in the `_check_steps.py` step, so `just check`/`just verify` went
# green on a stale provider catalog. The Python file-size and mutation-inert
# checks moved in from that step in the same round, so delegating cannot drop
# a check.)
check-architecture:
    @echo "🏛️  Checking architecture constraints..."
    uv run --all-packages python scripts/check_architecture.py --prompt-integrity
    uv run --all-packages python scripts/check_exception_baseline.py
    # RULE-04 Python file-size gate (moved here from `_check_steps.py`, T8b F2)
    uv run --all-packages python scripts/check_python_file_size.py
    uv run --all-packages python scripts/check_prompt_surface_contract.py
    uv run --all-packages python scripts/generate_provider_catalog.py --check
    # Hook-tiering ratchet (throughput T8/T9) — machine-pins which hooks run at
    # pre-push / manual / commit-msg so a whole-project hook cannot drift back
    # into the commit path (or be deleted) unnoticed.
    uv run --all-packages python scripts/check_pre_commit_gate_tiers.py
    # Review/report policy pin (throughput T11) — the marker in quality-gates.md,
    # its normative block and the pointer-only AGENTS/coordinator surfaces must
    # agree; no numeric restatement may creep back into the pointing docs.
    uv run --all-packages python scripts/check_review_policy_consistency.py
    uv run --all-packages python scripts/check_empty_kb_vars.py
    uv run --all-packages python scripts/check_frontmatter_schema.py
    # Mutation-inert convention (moved here from `_check_steps.py`, T8b F2) —
    # prevents the MutMut sandbox crash class documented in issue #146
    # (asset-reading tests reached via parents[N] must carry
    # @pytest.mark.mutation_inert).
    uv run --all-packages python scripts/checks/check_mutation_inert_assets.py
    # RULE-10 test-existence gate — mirrors the CI architecture job's step
    # (ci.yml: `check_test_coverage_gaps.py --fail-on-missing`, same flags)
    # so the local gate can no longer go green while CI goes red on it
    # (PR #236 run 37032595571). Measured ~0.6s (42 services, 0 missing).
    uv run --all-packages python scripts/check_test_coverage_gaps.py --fail-on-missing
    # RULE-04 frontend file-size gate — mirrors the pre-commit hook and the CI
    # frontend job's step (ci.yml: `python3 scripts/check_frontend_file_size.py`,
    # no flags) so the local architecture surface can no longer go green while
    # frontend sizes drift (PLAN-001 follow-up b / T13).
    uv run --all-packages python scripts/check_frontend_file_size.py

# Run ruff linter (with auto-fix)
lint:
    uv run --all-packages ruff check --fix apps/ packages/ scripts/ tests/ evals/
    uv run --all-packages ruff format apps/ packages/ scripts/ tests/ evals/

# Run ruff without fixing (for CI)
lint-check:
    uv run --all-packages ruff check apps/ packages/ scripts/ tests/ evals/
    uv run --all-packages ruff format --check apps/ packages/ scripts/ tests/ evals/

# Fast scoped ruff check (lint + format --check) for iterating on specific files/dirs.
# Whole-repo gate is `just lint-check`.
lint-file +files:
    uv run --all-packages ruff check {{files}}
    uv run --all-packages ruff format --check {{files}}

# Run pyright type checker
typecheck:
    uv run --all-packages pyright

# Fast scoped pyright for specific files. Whole-project gates are `just
# typecheck` (strict) and `just typecheck-tests` (basic).
# Path-aware config selection: files under tests/ are checked against
# tests/pyrightconfig.json (basic mode — same gate as `just typecheck-tests`);
# all other paths use the strict root config. The main config's `tests/`
# exclusion only affects directory discovery, so passing a test file explicitly
# would otherwise apply strict reportUnknown* rules no enforced gate cares about.
typecheck-file +files:
    #!/usr/bin/env bash
    set -euo pipefail
    prod=()
    tests=()
    for f in {{files}}; do
        case "$f" in
            tests|tests/*|./tests|./tests/*|"$PWD"/tests|"$PWD"/tests/*) tests+=("$f") ;;
            *) prod+=("$f") ;;
        esac
    done
    if [ "${#prod[@]}" -gt 0 ]; then
        uv run --all-packages pyright "${prod[@]}"
    fi
    if [ "${#tests[@]}" -gt 0 ]; then
        uv run --all-packages pyright --project tests/pyrightconfig.json "${tests[@]}"
    fi

# Run pyright on test files (basic mode, tests/pyrightconfig.json). Closes the
# gate gap: the main pyright config excludes tests/ for performance, so test-
# file type errors surface here and in `just check` — not only at commit time.
typecheck-tests:
    uv run --all-packages pyright --project tests/pyrightconfig.json

# Run secret-scanning gate (Gitleaks) — AUFG-05-09
# Blocks on new unapproved secrets; returns 127 with install guidance if the
# gitleaks binary is missing locally.
check-secrets:
    @echo "🔐 Checking for leaked secrets (Gitleaks)..."
    uv run --all-packages python scripts/check_secrets.py

# Run security checks
security: check-secrets
    uv run --all-packages bandit -c pyproject.toml -r apps/api/narrare packages/core/narrare_core scripts evals
    uv run --all-packages pip-audit

# Run non-mutating frontend lint and format checks
lint-frontend:
    cd packages/web && pnpm lint:check

# Run frontend lint/format auto-fixes
lint-frontend-fix:
    cd packages/web && pnpm lint

# Run frontend formatter
format-frontend:
    cd packages/web && pnpm format

# Run TypeScript type checking on frontend
typecheck-frontend:
    cd packages/web && pnpm type-check

# Build frontend (catches additional type/bundle errors)
build-frontend:
    cd packages/web && pnpm build

# Run all frontend checks (lint + typecheck + test)
check-frontend:
    @echo "🔍 Running frontend checks..."
    uv run --all-packages python scripts/check_frontend_file_size.py
    just lint-frontend
    just typecheck-frontend
    just test-frontend
    just check-vrt-contract
    @echo "✅ Frontend checks passed"

# Check VRT mock contract (ADR-059 BINDING) — every VRT spec must have
# catch-all route + expect.poll guard + timezoneId. Runs before VRT in CI.
check-vrt-contract:
    @echo "📐 Checking VRT mock contract (ADR-059 BINDING)..."
    cd packages/web && npx tsx scripts/check-vrt-mock-contract.ts

# ---------------------------------------------------------------------------
# Additional Checks
# ---------------------------------------------------------------------------

# Check feature adoption score (>= 0.85 PASS, 0.70-0.85 WARN, < 0.70 FAIL)
check-adoption:
    @echo "📈 Checking feature adoption score..."
    uv run --all-packages python scripts/check_adoption.py --evidence-dir .evidence

# Check approved architecture exceptions do not grow without ADR/user approval
check-exceptions:
    @echo "🧾 Checking approved exception baseline..."
    uv run --all-packages python scripts/check_exception_baseline.py

# Check TS/TSX file-size hard limits with no-growth baseline
check-frontend-size:
    @echo "📏 Checking frontend file-size limits..."
    uv run --all-packages python scripts/check_frontend_file_size.py

# Check feature-file frontmatter paths exist on disk (prevents phantom paths)
check-feature-paths:
    @echo "🛣️  Checking feature-file path accuracy..."
    uv run --all-packages python scripts/check_feature_path_accuracy.py

# Check Python file-size hard limits (RULE-04) with no-growth baseline
check-python-size:
    @echo "📏 Checking Python file-size limits..."
    uv run --all-packages python scripts/check_python_file_size.py

# Check SSOT consistency — CURRENT_STATE.md claims vs reality (blocking; matches CI)
check-ssot:
    @echo "📋 Checking CURRENT_STATE.md SSOT consistency..."
    uv run --all-packages python scripts/check_current_state_facts.py

# Check model registry against models.dev
check-models:
    @echo "🤖 Checking model registry..."
    uv run --all-packages python scripts/check_model_registry.py

# Check RULE-20 streaming compliance (SSE endpoints must use connectSSE in frontend)
check-streaming:
    @echo "📡 Checking RULE-20 streaming compliance..."
    uv run --all-packages python scripts/check_streaming_compliance.py

# Check ADR-043 / §16 AI interaction compliance (5 machine-checkable rules)
check-ai-ux:
    @echo "🤖 Checking ADR-043 AI interaction compliance..."
    uv run --all-packages python scripts/checks/check_ai_interaction_compliance.py

# Validate a commit message (for hook/CI use)
# Usage: just check-commit-msg "feat(core): add new prompt mode"
check-commit-msg msg:
    @printf '%s\n' {{quote(msg)}} | uv run --all-packages python scripts/check_commit_message.py

# Export OpenAPI schema to docs/
export-openapi:
    @echo "📤 Exporting OpenAPI schema..."
    uv run --all-packages --no-sync python scripts/export_openapi.py

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

# Validate prompt file structure (frontmatter, variables, security, size)
check-prompts:
    @echo "📝 Checking prompt structure..."
    uv run --all-packages python scripts/check_prompt_structure.py

# Same, but treat warnings as failures (CI mode)
check-prompts-strict:
    @echo "📝 Checking prompt structure (strict)..."
    uv run --all-packages python scripts/check_prompt_structure.py --strict

# Check locale sync between EN/DE/FR prompt variants
check-locale-sync:
    @echo "🌍 Checking locale sync..."
    uv run --all-packages python scripts/check_locale_sync.py

# Show locale sync with full details (all groups, including synced)
check-locale-sync-verbose:
    @echo "🌍 Checking locale sync (verbose)..."
    uv run --all-packages python scripts/check_locale_sync.py --verbose

# Check DE prompt translations for common quality issues (compounds, anglicisms)
check-prompts-de:
    @echo "🇩🇪 Checking DE prompt quality..."
    uv run --all-packages python scripts/prompt_quality_de.py

# Check aggregated system health score (HEALTHY >= 0.85, DEGRADED 0.70-0.85, CRITICAL < 0.70)
check-health:
    @echo "🏥 Checking system health..."
    uv run --all-packages python scripts/check_system_health.py

# List all bundled prompt modes with locale coverage
prompt-list:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "📋 Bundled prompt modes:"
    echo ""
    for dir in $(find packages/core/narrare_core/prompts/_bundled/ -mindepth 2 -maxdepth 2 -type d \( -name "en" -o -name "de" -o -name "fr" \) | sort); do
        mode=$(dirname "$dir" | sed 's|.*/_bundled/||')
        locale=$(basename "$dir")
        echo "  $mode [$locale]"
    done | sort -u

# Show prompt statistics (count per category, locale coverage, line counts)
prompt-stats:
    #!/usr/bin/env bash
    set -euo pipefail
    BUNDLED="packages/core/narrare_core/prompts/_bundled"
    echo "📊 Prompt Statistics"
    echo "==================="
    echo ""
    echo "Total .md files:  $(find "$BUNDLED" -name '*.md' | wc -l)"
    echo "System prompts:   $(find "$BUNDLED" -name 'system.md' | wc -l)"
    echo ""
    echo "By category:"
    for cat in analysis chat generation kb meta planning wiki writing; do
        count=$(find "$BUNDLED/$cat" -name 'system.md' 2>/dev/null | wc -l)
        [ "$count" -gt 0 ] && echo "  $cat: $count files"
    done
    echo ""
    echo "By locale:"
    for loc in en de fr; do
        count=$(find "$BUNDLED" -path "*/$loc/*/system.md" -o -path "*/$loc/system.md" | wc -l)
        echo "  $loc: $count prompts"
    done
    echo ""
    echo "Largest prompts (by lines):"
    find "$BUNDLED" -name 'system.md' -exec wc -l {} + | sort -rn | head -6

# ---------------------------------------------------------------------------
# Release
# ---------------------------------------------------------------------------

# Show current version
version:
    @cat CHANGELOG.md | grep "## \[" | head -1

# Preview changelog for unreleased changes
changelog:
    @cat CHANGELOG.md | awk '/## \[Unreleased\]/,/## \[/' | head -50

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

# Remove build artifacts and caches
clean:
    uv run python scripts/clean_caches.py

# Aggressive cleanup: free disk space by clearing caches and dangling data
cleanup:
    @echo "🧹 Cleaning up disk space..."
    @echo "  Clearing uv cache..."
    uv cache clean --force 2>/dev/null || true
    @echo "  Pruning Docker dangling images..."
    docker image prune --all --force 2>/dev/null || true
    @echo "  Pruning pnpm store..."
    pnpm store prune 2>/dev/null || true
    @echo "  Cleaning __pycache__ outside project dirs..."
    find ~ -name __pycache__ -type d -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/.git/*' -not -path '*/pnpm-store/*' -exec rm -rf {} + 2>/dev/null || true
    @echo "✅ Cleanup complete"

# Tail all service logs
logs:
    @if command -v docker >/dev/null 2>&1; then \
        docker compose -f docker-compose.dev.yml logs -f; \
    else \
        echo "ℹ️  Docker not available — cannot tail service logs (dev container?)"; \
    fi

# Open Python REPL with app context
shell:
    #!/usr/bin/env bash
    cd apps/api && uv run python -c "
    import asyncio
    from narrare._app.main import app
    from narrare._app.database import get_async_session
    print('Narrare shell ready. App:', app.title)
    " && uv run python -i -c ""

# Show dependency tree
deps:
    uv tree

# Update all dependencies to latest compatible versions
deps-update:
    uv sync --upgrade --all-packages --group dev --extra nlp
    cd packages/web && pnpm update
    @echo "⚠️  Run 'just check', 'just test', and 'just check-frontend' after updating dependencies"

# Install/update pre-commit hooks
hooks-update:
    pre-commit autoupdate
    pre-commit install --install-hooks

# ---------------------------------------------------------------------------
# Full check
# ---------------------------------------------------------------------------

# Full pre-merge check (everything, strict mode)
#
# SSOT (check_current_state_facts.py) is blocking — matches CI's architecture
# job. The volatility-policy checker currently exits 0 (verified after the
# regex false-positive fix, commit 41efa086), so a non-zero exit is a real
# regression and must block the merge.
check-full: check check-python-size check-streaming check-ai-ux check-secrets check-prompts-strict check-locale-sync check-prompts-de check-adoption check-models check-health check-feature-paths
    uv run --all-packages python scripts/check_current_state_facts.py
    @echo "✅ All checks passed — ready to merge"

# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

# Externe Skills aktualisieren (.agents/skills + vendored superpowers) — danach git diff reviewen.
skills-update:
    bash scripts/update-skills.sh
