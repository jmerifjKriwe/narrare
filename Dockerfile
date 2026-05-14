# ============================================================================
# Narrare — Production Dockerfile (multi-stage)
# ============================================================================
#
# Single image running both FastAPI backend and Next.js frontend:
#   - FastAPI  (uvicorn)    on 127.0.0.1:8000  (internal, proxied by Next.js)
#   - Next.js  (standalone) on 0.0.0.0:3000    (external)
#
# Build:  docker build -t narrare .
# Run:    docker run -p 3000:3000 --env-file .env narrare
#
# BuildKit is required for cache mounts (default in Docker >= 23):
#   DOCKER_BUILDKIT=1 docker build -t narrare .
#
# ---------------------------------------------------------------------------
# Recommended .dockerignore (create alongside this file):
#
#   .git/
#   .venv/
#   .env
#   **/node_modules/
#   **/__pycache__/
#   **/.pytest_cache/
#   **/.ruff_cache/
#   **/.next/
#   **/*.egg-info/
#   **/*.pyc
#   tests/
#   docs/
#   scripts/local/
#   .code-review-graph/
#   .opencode/
# ============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Install Python dependencies via uv
# ---------------------------------------------------------------------------
FROM python:3.14-slim-bookworm AS build-python

# uv — fast Python package installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Workspace definition + lockfile (changes infrequently)
COPY pyproject.toml uv.lock ./

# Workspace member manifests
COPY apps/api/pyproject.toml     apps/api/
COPY packages/core/pyproject.toml packages/core/
COPY packages/i18n/pyproject.toml packages/i18n/

# Python package sources (required for editable workspace installs)
COPY apps/api/narrare/           apps/api/narrare/
COPY packages/core/narrare_core/ packages/core/narrare_core/
COPY packages/i18n/narrare_i18n/ packages/i18n/narrare_i18n/

# Production deps only, pinned to the lockfile
# --mount=type=cache persists the uv download cache across builds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --all-packages

# ---------------------------------------------------------------------------
# Stage 2: Build Next.js frontend (standalone output)
# ---------------------------------------------------------------------------
FROM node:24-slim-bookworm AS build-frontend

# Enable pnpm via corepack
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# Workspace config + lockfile first (maximises Docker layer cache hits)
COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages/web/package.json packages/web/

# Install Node.js dependencies
# --mount=type=cache persists the pnpm content-addressable store
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

# Full web source + build
COPY packages/web/ packages/web/
RUN pnpm --filter narrare-web build

# ---------------------------------------------------------------------------
# Stage 3: Minimal production runtime
# ---------------------------------------------------------------------------
FROM python:3.14-slim-bookworm AS runtime

# Install Node.js 24 runtime (Next.js standalone server needs the node binary)
# and curl (kept for the HEALTHCHECK probe)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Python virtual environment (production deps only) ---
COPY --from=build-python /app/.venv /app/.venv

# --- Next.js standalone output ---
# In a pnpm workspace the standalone directory preserves the workspace layout,
# so server.js ends up at <standalone>/packages/web/server.js.
COPY --from=build-frontend \
    /app/packages/web/.next/standalone  /app/frontend

# Static assets and public/ are NOT included in standalone — copy separately
COPY --from=build-frontend \
    /app/packages/web/.next/static      /app/frontend/packages/web/.next/static
COPY --from=build-frontend \
    /app/packages/web/public             /app/frontend/packages/web/public

# --- Entrypoint ---
COPY scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# ---------------------------------------------------------------------------
# Runtime defaults (override with docker run -e or --env-file)
# ---------------------------------------------------------------------------
# PATH — make venv binaries (uvicorn, alembic, …) available by default
# NEXT_PUBLIC_API_URL — the Next.js rewrite target (same-container backend)
ENV PATH="/app/.venv/bin:${PATH}" \
    NEXT_PUBLIC_API_URL="http://localhost:8000"

# External port (Next.js frontend)
EXPOSE 3000

# Liveness probe — hits the FastAPI /health endpoint on the internal port
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8000/health > /dev/null 2>&1 || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
