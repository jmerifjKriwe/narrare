# Narrare v2. One backend under app/, one web app under web/.
# 27 public recipes; private helpers start with `_`.
# .env is the whole configuration surface; a missing file is fine.
set dotenv-load := true

# Start the Postgres services the app and the tests need.
dev-services:
    docker compose -f docker-compose.dev.yml up -d --wait postgres postgres_test

# Stop the Postgres services.
dev-services-stop:
    docker compose -f docker-compose.dev.yml down

# The ports of both dev stacks are the E2E env pair, not literals: the same
# NARRE_E2E_API_PORT / NARRE_E2E_WEB_PORT configures `just dev` and the E2E
# stacks (stack.py forwards its environment to `pnpm dev`, which vite reads),
# so two stacks on one machine are an env difference, not a code edit.

# API with reload on the configured port (default 8000).
dev-api:
    uv run uvicorn app.api.main:app --reload --port "${NARRE_E2E_API_PORT:-8000}"

# Web app on the configured port (default 3100): vite reads
# NARRE_E2E_WEB_PORT itself, no flag needed here.
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
    pre-commit install --install-hooks
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

# Ruff and Biome: check only.
lint:
    uv run ruff check app scripts
    uv run ruff format --check app scripts
    pnpm exec biome lint --error-on-warnings

# Pyright for the backend, tsc for the web app.
typecheck:
    uv run pyright
    pnpm --dir web typecheck

# Who calls a symbol: just callers app/kernel/llm/repositories.py:69
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

# Every integration test with coverage, for the main-push report.
test-cov:
    uv run pytest app --cov --cov-branch --cov-report=xml --junitxml=junit.xml -o junit_family=legacy

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
    uv run pytest $paths -v -m "e2e and not showcase" --timeout=60

# Bounded Atheris run over the interchange parser: just fuzz 60 (seconds).
# Seeds are fuzz/corpus; new units and a finding land in the gitignored
# fuzz/workdir/ and fuzz/crash-*.
fuzz seconds="300":
    mkdir -p fuzz/workdir
    uv run --group fuzz python -m scripts.fuzz_archive fuzz/workdir fuzz/corpus -max_total_time={{seconds}} -artifact_prefix=fuzz/

# Web unit tests.
test-frontend:
    pnpm --dir web test

# Only the web tests the working tree's change reaches — the inner loop for
# frontend work, mirroring the pre-commit hook. Full suite via test-frontend.
test-frontend-changed:
    pnpm --dir web exec vitest run --changed HEAD

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
[positional-arguments]
db-revision message:
    NARRE_DATABASE_URL="${NARRE_DATABASE_URL:-postgresql+asyncpg://narrare:narrare@localhost:5432/narrare_v2_dev}" \
        uv run alembic revision --autogenerate -m "$1"

# A psql shell on the development database.
db-shell:
    docker compose -f docker-compose.dev.yml exec postgres psql -U narrare -d narrare_v2_dev

# Write the OpenAPI document, the capability views and the typed web client.
generate:
    uv run python -m scripts.export_openapi
    uv run python -m scripts.generate_capabilities
    pnpm --dir web generate

# Compares only the generated paths, so unrelated dirt in the working tree does
# not matter. CI runs it on every PR and every nightly.
# Regenerate and fail when the committed generated files differ.
check-generated:
    #!/usr/bin/env bash
    set -euo pipefail
    just generate
    changed=$(git status --porcelain --untracked-files=all -- \
        app/generated web/lib/generated \
        web/lib/api/openapi.json web/lib/api/schema.d.ts docs/user/INDEX.md)
    if [ -n "$changed" ]; then
        printf '%s\n' "$changed" >&2
        echo "committed generated files are stale: commit the regenerated files, or revert the input change" >&2
        exit 1
    fi

# Scaffold a capability folder: just new-capability notes
new-capability name:
    uv run python -m scripts.new_capability {{name}}
