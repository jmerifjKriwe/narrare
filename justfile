# Narrare v2. One backend under app/, one web app under web/.
# 28 public recipes; private helpers start with `_`.
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
    @nvmrc_major=$(sed -e 's/^v//' -e 's/[[:space:]]//g' .nvmrc 2>/dev/null || true); \
        nvmrc_major=${nvmrc_major%%.*}; \
        node_version=$(node --version 2>/dev/null || true); \
        node_major=${node_version#v}; \
        node_major=${node_major%%.*}; \
        echo "Node major: .nvmrc names ${nvmrc_major:-unknown}; node --version runs ${node_version:-not found} (major ${node_major:-unknown})"; \
        if [ -n "$nvmrc_major" ] && [ -n "$node_major" ] && [ "$nvmrc_major" != "$node_major" ]; then \
            echo "Node major differs from .nvmrc: run 'nvm install' then 'nvm use' (both read .nvmrc)"; \
        fi
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

# Every integration test, including the script tests under scripts/tests.
test:
    uv run pytest app scripts/tests -v

# One file or one node: just test-file app/capabilities/chat/tests/test_chat.py
test-file file:
    uv run pytest {{file}} -v

# Every integration test with coverage, for the main-push report. Both roots,
# like `test`.
test-cov:
    uv run pytest app scripts/tests --cov --cov-branch --cov-report=xml --junitxml=junit.xml -o junit_family=legacy

# Every capability E2E: real browser, real API, real Postgres. `all` or a
# capability name overrides the affected default. Workers: the second argument,
# else NARRE_E2E_WORKERS, else two when the machine has 6 GB to spare and one
# below that — this host OOM-killed a browser on a nine-gigabyte box shared with
# other sessions (#776). An attached instance (the container gate) runs
# serially: it has one database and no stack per worker.
test-e2e scope="affected" workers="":
    #!/usr/bin/env bash
    set -euo pipefail
    workers="{{workers}}"
    paths=$(uv run python -m scripts.affected --paths "{{scope}}" --worktree)
    if [ -z "$paths" ]; then
      echo "no capability touched — no browser suite owed"
      exit 0
    fi
    if [ -z "${workers}" ]; then
      available_mb=$(awk '/^MemAvailable:/ {printf "%d", $2 / 1024}' /proc/meminfo)
      if [ "${available_mb}" -ge 6000 ]; then workers=2; else workers=1; fi
      echo "E2E on ${workers} worker(s); ${available_mb} MB available"
    else
      echo "E2E on ${workers} worker(s)"
    fi
    uv run pytest $paths -v -m e2e --timeout=60 -n "$workers"

# One E2E file, node or `-k` selection with the suite's own marker and timeout
# (no affected resolver): just test-e2e-file <file> --lf — setup's suite is
# back; more return with each rebuilt wave.
[positional-arguments]
test-e2e-file *args:
    uv run pytest {{args}} -v -m e2e --timeout=60

# Bounded Atheris run over the interchange parser: just fuzz 60 (seconds).
# Seeds are fuzz/corpus; new units and a finding land in the gitignored
# fuzz/workdir/ and fuzz/crash-*.
fuzz seconds="300":
    mkdir -p fuzz/workdir
    uv run --group fuzz python -m scripts.fuzz_archive fuzz/workdir fuzz/corpus -max_total_time={{seconds}} -artifact_prefix=fuzz/

# Web unit tests.
test-frontend:
    pnpm --dir web test

# Web unit tests with V8 coverage (LCOV in web/coverage). Used for SonarCloud.
# The V8 reporter writes SF paths relative to web/ (vitest's root): capability
# components appear as ../app/capabilities/... and SonarCloud's scanner fails
# to resolve that form against the repo root — every capability web file has
# read 0% since allowExternal turned them on. The normalization rewrites every
# SF to a repo-root-relative path (../app/x -> app/x, bare web paths ->
# web/x), the form sonar-scanner documents; web/-rooted entries keep matching.
test-frontend-cov:
    pnpm --dir web test:coverage
    python3 scripts/sonar_lcov.py web/coverage/lcov.info

# Only the web tests the working tree's change reaches — the inner loop for
# frontend work, mirroring the pre-commit hook. Full suite via test-frontend.
test-frontend-changed:
    pnpm --dir web exec vitest run --changed HEAD

# Production build of the web app.
build:
    pnpm --dir web build

# Capture the README's images from the real app (needs dev-services + playwright chromium).
screenshots *args:
    uv run python -m scripts.screenshots {{args}}

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
# The URL is the application's own resolution (as db-init), so a given
# NARRE_DATABASE_URL or NARRE_DEV_DB_PORT reaches alembic unchanged.
[positional-arguments]
db-revision message:
    NARRE_DATABASE_URL="$(uv run python -c 'from app.kernel.db.session import DATABASE_URL; print(DATABASE_URL)')" \
        uv run alembic revision --autogenerate -m "$1"

# A psql shell on the development database.
db-shell:
    docker compose -f docker-compose.dev.yml exec postgres psql -U narrare -d narrare_v2_dev

# Write the OpenAPI document, the capability views and the typed web client.
generate:
    uv run python -m scripts.generate_capabilities
    uv run python -m scripts.export_openapi
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
        web/lib/api/openapi.json web/lib/api/schema.d.ts docs/user/INDEX.md docs/user/help-coverage.md)
    if [ -n "$changed" ]; then
        printf '%s\n' "$changed" >&2
        echo "committed generated files are stale: commit the regenerated files, or revert the input change" >&2
        exit 1
    fi

# Scaffold a capability folder: just new-capability notes
new-capability name:
    uv run python -m scripts.new_capability {{name}}

# SonarCloud: just sonar qg | issues [--all] [--severity ...] | measures | hotspots
[positional-arguments]
sonar *args:
    uv run python -m scripts.sonar "$@"
