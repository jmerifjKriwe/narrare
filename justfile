# Narrare v2. One backend under app/, one web app under web/.
# 23 public recipes; private helpers start with `_`.
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
    just db-init

# Fast gate: lint and types. The under-ten-seconds one.
check:
    just lint
    just typecheck

# check, the integration tests, the web unit suite, the production build and
# the E2E — the E2E leg narrows like test-e2e's, one scope for both.
# Full gate: check, every suite and the web build; affected by default, `all` for everything.
verify scope="affected":
    just check
    just test
    just test-frontend
    just build
    just test-e2e {{scope}}

# Ruff: check and format check.
lint:
    uv run ruff check app scripts
    uv run ruff format --check app scripts

# Pyright for the backend, tsc for the web app.
typecheck:
    uv run pyright
    pnpm --dir web typecheck

# Who calls a symbol: just callers app/kernel/llm/profiles.py ordered
[positional-arguments]
callers *args:
    uv run python -m scripts.callers "$@"

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

# Every capability E2E: real browser, real API, real Postgres. `all` or a
# capability name overrides the default;
# by default only the suites the change touches run.
test-e2e scope="affected":
    #!/usr/bin/env bash
    set -euo pipefail
    paths=$(uv run python -m scripts.affected --paths "{{scope}}" --worktree)
    if [ -z "$paths" ]; then
      echo "no capability touched — no browser suite owed"
      exit 0
    fi
    uv run pytest $paths -v -m e2e --timeout=60

# Web unit tests.
test-frontend:
    pnpm --dir web test

# Production build of the web app.
build:
    pnpm --dir web build

# Bring the development database to the migration history's head. A missing
# schema is created; an existing one keeps its tables and is upgraded.
db-init:
    uv run python -m app.kernel.db.init

# Recreate the development database: drop it, then end in the same upgrade
# db-init ends in.
db-reset:
    @echo "This drops narrare_v2_dev. Ctrl+C to cancel."
    @sleep 3
    docker compose -f docker-compose.dev.yml exec -T postgres \
        psql -U narrare -d postgres -c "DROP DATABASE IF EXISTS narrare_v2_dev WITH (FORCE)"
    docker compose -f docker-compose.dev.yml exec -T postgres \
        psql -U narrare -d postgres -c "CREATE DATABASE narrare_v2_dev"
    just db-init

# Draft a revision from the models: just db-revision "add chapters.word_count"
db-revision message:
    NARRE_DATABASE_URL="${NARRE_DATABASE_URL:-postgresql+asyncpg://narrare:narrare@localhost:5432/narrare_v2_dev}" \
        uv run alembic revision --autogenerate -m "{{message}}"

# A psql shell on the development database.
db-shell:
    docker compose -f docker-compose.dev.yml exec postgres psql -U narrare -d narrare_v2_dev

# Write the OpenAPI document, the capability views and the typed web client.
generate:
    uv run python -m scripts.export_openapi
    uv run python -m scripts.generate_capabilities
    pnpm --dir web generate

# Scaffold a capability folder: just new-capability notes
new-capability name:
    uv run python -m scripts.new_capability {{name}}
