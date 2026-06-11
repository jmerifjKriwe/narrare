# Narrare — Task Runner
# Requires: just (https://just.systems)
# Usage: just <command>

set dotenv-load := true
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
_psql-sql db sql *args:
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
_psql-shell db *args:
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
dev-setup:
    @echo "🚀 Setting up Narrare..."
    @if [ ! -f .env ]; then cp .env.example .env && echo "📋 Created .env — add your API keys"; fi
    uv sync --frozen --all-packages --group dev --extra nlp
    just install-nlp-models
    pre-commit install --install-hooks
    pnpm install
    @echo "⏳ Starting services..."
    just _ensure-services
    just db-migrate
    uv run python scripts/seed_dev_user.py
    @echo "✅ Ready! Run 'just dev' to start."

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

# Start TaskIQ worker only (requires broker module — Phase 5+)
dev-worker:
    cd apps/api && uv run taskiq worker narrare.tasks.broker:broker \
        --fs-discover \
        --log-level DEBUG

# Start Docker services (postgres + redis)
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

# Run all tests (parallel)
test:
    uv run pytest tests/ -v -n auto

# Run unit tests only (fast, no Docker needed, parallel)
test-unit:
    uv run pytest tests/unit/ -v -n auto --dist loadfile

# Run tests single-threaded (for debugging)
test-single file="tests/":
    uv run pytest {{file}} -v -p no:randomly

# Run integration tests (requires Docker services)
test-integration:
    just _ensure-services
    uv run pytest tests/integration/ -v

# Run with coverage report
test-cov:
    uv run pytest tests/ --cov --cov-report=term-missing --cov-report=html
    @echo "Coverage report: htmlcov/index.html"

# Run one or more specific test files
# Usage: just test-file tests/unit/core/llm/test_gateway.py
# Usage: just test-file tests/unit/core/llm/test_gateway.py tests/unit/core/llm/test_other.py
test-file +files:
    uv run pytest {{files}} -v

# Run tests matching a pattern
# Usage: just test-match "test_gateway"
test-match pattern:
    uv run pytest tests/ -v -k "{{pattern}}"

# Run E2E tests (requires full stack: just dev + dev-services)
test-e2e:
    uv run pytest tests/e2e/ -v -m e2e --timeout=60

# Run frontend tests (Vitest)
test-frontend:
    cd packages/web && pnpm test

# Run frontend tests with coverage (fails if thresholds not met)
test-frontend-coverage:
    cd packages/web && pnpm test:coverage

# Run all tests (backend + frontend)
test-all: test test-frontend

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

# Run all checks with compact summary (architecture + lint + typecheck + security + frontend)
check:
    uv run python scripts/run_checks.py

# Run all checks with full tool output
check-verbose:
    uv run python scripts/run_checks.py --verbose

# Run architecture constraint checker
check-architecture:
    @echo "🏛️  Checking architecture constraints..."
    uv run python scripts/check_architecture.py
    uv run python scripts/check_exception_baseline.py

# Run ruff linter (with auto-fix)
lint:
    uv run ruff check --fix apps/ packages/ scripts/ tests/ evals/
    uv run ruff format apps/ packages/ scripts/ tests/ evals/

# Run ruff without fixing (for CI)
lint-check:
    uv run ruff check apps/ packages/ scripts/ tests/ evals/
    uv run ruff format --check apps/ packages/ scripts/ tests/ evals/

# Run pyright type checker
typecheck:
    uv run pyright

# Run security checks
security:
    uv run bandit -c pyproject.toml -r apps/api/narrare packages/core/narrare_core
    uv run pip-audit

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
    uv run python scripts/check_frontend_file_size.py
    just lint-frontend
    just typecheck-frontend
    just test-frontend
    @echo "✅ Frontend checks passed"

# ---------------------------------------------------------------------------
# Additional Checks
# ---------------------------------------------------------------------------

# Check feature adoption score (>= 0.85 PASS, 0.70-0.85 WARN, < 0.70 FAIL)
check-adoption:
    @echo "📈 Checking feature adoption score..."
    uv run python scripts/check_adoption.py

# Check approved architecture exceptions do not grow without ADR/user approval
check-exceptions:
    @echo "🧾 Checking approved exception baseline..."
    uv run python scripts/check_exception_baseline.py

# Check TS/TSX file-size hard limits with no-growth baseline
check-frontend-size:
    @echo "📏 Checking frontend file-size limits..."
    uv run python scripts/check_frontend_file_size.py

# Check Python file-size hard limits (RULE-04) with no-growth baseline
check-python-size:
    @echo "📏 Checking Python file-size limits..."
    uv run python scripts/check_python_file_size.py

# Check SSOT consistency — CURRENT_STATE.md claims vs reality (warn-only)
check-ssot:
    @echo "📋 Checking CURRENT_STATE.md SSOT consistency..."
    uv run python scripts/check_current_state_facts.py

# Check model registry against models.dev
check-models:
    @echo "🤖 Checking model registry..."
    uv run python scripts/check_model_registry.py

# Check RULE-20 streaming compliance (SSE endpoints must use connectSSE in frontend)
check-streaming:
    @echo "📡 Checking RULE-20 streaming compliance..."
    uv run python scripts/check_streaming_compliance.py

# Check ADR-043 / §16 AI interaction compliance (5 machine-checkable rules)
check-ai-ux:
    @echo "🤖 Checking ADR-043 AI interaction compliance..."
    uv run python scripts/checks/check_ai_interaction_compliance.py

# Validate a commit message (for hook/CI use)
# Usage: just check-commit-msg "feat(core): add new prompt mode"
check-commit-msg msg:
    @echo "$$msg" | uv run python scripts/check_commit_message.py

# Export OpenAPI schema to docs/
export-openapi:
    @echo "📤 Exporting OpenAPI schema..."
    cd apps/api && uv run python ../../scripts/export_openapi.py

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

# Validate prompt file structure (frontmatter, variables, security, size)
check-prompts:
    @echo "📝 Checking prompt structure..."
    uv run python scripts/check_prompt_structure.py

# Same, but treat warnings as failures (CI mode)
check-prompts-strict:
    @echo "📝 Checking prompt structure (strict)..."
    uv run python scripts/check_prompt_structure.py --strict

# Check locale sync between EN/DE/FR prompt variants
check-locale-sync:
    @echo "🌍 Checking locale sync..."
    uv run python scripts/check_locale_sync.py

# Show locale sync with full details (all groups, including synced)
check-locale-sync-verbose:
    @echo "🌍 Checking locale sync (verbose)..."
    uv run python scripts/check_locale_sync.py --verbose

# Check DE prompt translations for common quality issues (compounds, anglicisms)
check-prompts-de:
    @echo "🇩🇪 Checking DE prompt quality..."
    uv run python scripts/prompt_quality_de.py

# Check aggregated system health score (HEALTHY >= 0.85, DEGRADED 0.70-0.85, CRITICAL < 0.70)
check-health:
    @echo "🏥 Checking system health..."
    uv run python scripts/check_system_health.py

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
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name ".coverage" -delete 2>/dev/null || true
    @echo "✅ Cleaned"

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

# Full pre-merge check (everything, strict mode, SSOT warn-only)
#
# check-ssot is warn-only: it reports discrepancies but does not block the merge.
# The `|| true` prevents its non-zero exit code from failing the entire recipe.
check-full: check check-python-size check-streaming check-ai-ux check-prompts-strict check-locale-sync check-prompts-de check-adoption check-models check-health
    -uv run python scripts/check_current_state_facts.py || true
    @echo "✅ All checks passed — ready to merge"
