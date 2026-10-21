# Narrare v2. One backend under app/, one web app under web/.
# 22 public recipes; private helpers start with `_`.
# .env is the whole configuration surface; a missing file is fine.
set dotenv-load := true

# Start the Postgres services the app and the tests need.
dev-services:
    docker compose -f docker-compose.dev.yml up -d --wait postgres postgres_test

# Stop the Postgres services.
dev-services-stop:
    docker compose -f docker-compose.dev.yml down

# API with reload on :8000.
dev-api:
    uv run uvicorn app.api.main:app --reload --port 8000

# Web app on :3100.
dev-web:
    pnpm --dir web dev

# API and web together. Ctrl+C stops both.
dev:
    #!/usr/bin/env bash
    set -euo pipefail
    just dev-services
    just dev-api & api=$!
    just dev-web & web=$!
    trap 'kill $api $web 2>/dev/null || true' EXIT
    wait

# First run: python env, web deps, hooks, services, schema.
dev-setup:
    uv sync
    pnpm install
    pre-commit install --install-hooks --hook-type pre-commit --hook-type pre-push
    just dev-services
    just db-migrate

# Fast gate: lint and types. The under-ten-seconds one.
check:
    just lint
    just typecheck

# Full gate: the fast one plus every suite and the production build.
verify:
    just check
    just test
    just test-frontend
    just build
    just test-e2e

# Ruff: check and format check.
lint:
    uv run ruff check app scripts
    uv run ruff format --check app scripts

# Pyright, whole project.
typecheck:
    uv run pyright

# Apply formatting and the import fixes ruff can make.
format:
    uv run ruff check --fix app scripts
    uv run ruff format app scripts

# Every integration test.
test:
    uv run pytest app/ -v

# One file or one node: just test-file app/capabilities/chat/tests/test_chat.py
test-file file:
    uv run pytest {{file}} -v

# Every capability E2E: real browser, real API, real Postgres.
test-e2e:
    uv run pytest app/capabilities/*/e2e/ -v -m e2e --timeout=60

# Web unit tests.
test-frontend:
    pnpm --dir web test

# Production build of the web app.
build:
    pnpm --dir web build

# Apply the schema migrations.
db-migrate:
    uv run alembic -c app/kernel/db/alembic.ini upgrade head

# A new migration from the model diff: just db-revision "add x"
db-revision message:
    uv run alembic -c app/kernel/db/alembic.ini revision --autogenerate -m "{{message}}"

# Recreate the development database and migrate it.
db-reset:
    @echo "This drops narrare_v2_dev. Ctrl+C to cancel."
    @sleep 3
    docker compose -f docker-compose.dev.yml exec -T postgres \
        psql -U narrare -d postgres -c "DROP DATABASE IF EXISTS narrare_v2_dev WITH (FORCE)"
    docker compose -f docker-compose.dev.yml exec -T postgres \
        psql -U narrare -d postgres -c "CREATE DATABASE narrare_v2_dev"
    just db-migrate

# A psql shell on the development database.
db-shell:
    docker compose -f docker-compose.dev.yml exec postgres psql -U narrare -d narrare_v2_dev

# Write the OpenAPI document the web app reads.
generate:
    uv run python -m scripts.export_openapi

# Scaffold a capability folder: just new-capability notes
new-capability name:
    uv run python -m scripts.new_capability {{name}}
