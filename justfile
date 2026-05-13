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

# Check if docker is available (skip in dev container where services already run)
[private]
_ensure-services:
    @if command -v docker >/dev/null 2>&1; then \
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

# Run SQL via psql directly (dev container) or docker compose exec (host)
[private]
_psql-sql db sql *args:
    @if command -v psql >/dev/null 2>&1; then \
        psql -U narrare -d {{db}} -c "{{sql}}"; \
    elif command -v docker >/dev/null 2>&1; then \
        docker compose -f docker-compose.dev.yml exec postgres psql -U narrare -d {{db}} -c "{{sql}}"; \
    else \
        echo "❌ Neither psql nor docker available — cannot run SQL"; exit 1; \
    fi

# Open psql shell via psql directly (dev container) or docker compose exec (host)
[private]
_psql-shell db *args:
    @if command -v psql >/dev/null 2>&1; then \
        psql -U narrare -d {{db}}; \
    elif command -v docker >/dev/null 2>&1; then \
        docker compose -f docker-compose.dev.yml exec postgres psql -U narrare -d {{db}}; \
    else \
        echo "❌ Neither psql nor docker available — cannot open shell"; exit 1; \
    fi

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

# First-time setup: install all dependencies, create .env, run migrations
dev-setup:
    @echo "🚀 Setting up Narrare..."
    @if [ ! -f .env ]; then cp .env.example .env && echo "📋 Created .env — add your API keys"; fi
    uv sync --all-packages --group dev
    pre-commit install --install-hooks
    @if [ -f packages/web/package.json ]; then cd packages/web && pnpm install; fi
    @echo "⏳ Starting services..."
    just _ensure-services
    just db-migrate
    uv run python scripts/seed_dev_user.py
    @echo "✅ Ready! Run 'just dev' to start."

# Generate a secure secret key
generate-secret:
    uv run python -c "import secrets; print(secrets.token_hex(32))"

# ---------------------------------------------------------------------------
# Development servers
# ---------------------------------------------------------------------------

# Start all services (API + frontend + worker)
dev:
    @echo "Starting all services..."
    just _ensure-services
    @trap 'kill %1 %2 %3 2>/dev/null' INT; \
    just dev-api & \
    just dev-frontend & \
    just dev-worker & \
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

# Start TaskIQ worker only
dev-worker:
    cd apps/api && uv run taskiq worker narrare.core.tasks.broker:broker \
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
    just _psql-sql narrare_dev "DROP DATABASE IF EXISTS narrare_dev; CREATE DATABASE narrare_dev;"
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
    uv run pytest tests/unit/ -v -n auto

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

# Run a specific test file
# Usage: just test-file tests/unit/core/llm/test_gateway.py
test-file file:
    uv run pytest {{file}} -v

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

# Run ruff linter (with auto-fix)
lint:
    uv run ruff check --fix apps/ packages/ scripts/ tests/
    uv run ruff format apps/ packages/ scripts/ tests/

# Run ruff without fixing (for CI)
lint-check:
    uv run ruff check apps/ packages/ scripts/ tests/
    uv run ruff format --check apps/ packages/ scripts/ tests/

# Run pyright type checker
typecheck:
    uv run pyright

# Run security checks
security:
    uv run bandit -c pyproject.toml -r apps/api/narrare packages/core/narrare_core
    uv run pip-audit

# Run ESLint on frontend
lint-frontend:
    cd packages/web && pnpm lint

# Run TypeScript type checking on frontend
typecheck-frontend:
    cd packages/web && pnpm type-check

# Build frontend (catches additional type/bundle errors)
build-frontend:
    cd packages/web && pnpm build

# Run all frontend checks (lint + typecheck + test)
check-frontend:
    @echo "🔍 Running frontend checks..."
    just lint-frontend
    just typecheck-frontend
    just test-frontend
    @echo "✅ Frontend checks passed"

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
    uv sync --upgrade --all-packages --dev
    cd packages/web && pnpm update
    @echo "⚠️  Run 'just check', 'just test', and 'just check-frontend' after updating dependencies"

# Install/update pre-commit hooks
hooks-update:
    pre-commit autoupdate
    pre-commit install --install-hooks
