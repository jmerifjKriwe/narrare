#!/usr/bin/env bash
# ============================================================================
# Narrare — Container entrypoint
# ============================================================================
# Starts both services in a single container:
#   1. FastAPI backend  (uvicorn on 127.0.0.1:8000 — internal only)
#   2. Next.js frontend (standalone on 0.0.0.0:3000 — external)
#
# If either process exits, the other is terminated and the container stops.
# SIGTERM / SIGINT / SIGQUIT are propagated to both children for graceful
# shutdown.
# ============================================================================
set -euo pipefail

# --- Signal handling --------------------------------------------------------
cleanup() {
    echo "[entrypoint] Shutting down (received signal)…" >&2
    kill "$UVICORN_PID" "$NEXT_PID" 2>/dev/null || true
    wait
}

trap cleanup SIGTERM SIGINT SIGQUIT

# --- FastAPI backend --------------------------------------------------------
echo "[entrypoint] Starting FastAPI backend on 127.0.0.1:8000" >&2
cd /app

.venv/bin/uvicorn narrare._app.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    &
UVICORN_PID=$!

# --- Next.js frontend -------------------------------------------------------
echo "[entrypoint] Starting Next.js frontend on 0.0.0.0:3000" >&2

# The standalone output preserves the workspace directory structure:
# /app/frontend/packages/web/server.js
cd /app/frontend/packages/web

HOSTNAME=0.0.0.0 PORT=3000 node server.js &
NEXT_PID=$!

# --- Wait for either process to exit ----------------------------------------
wait -n "$UVICORN_PID" "$NEXT_PID"
EXIT_CODE=$?

# One process exited — terminate the other and propagate the exit code
echo "[entrypoint] A process exited (code=$EXIT_CODE), stopping remaining…" >&2
kill "$UVICORN_PID" "$NEXT_PID" 2>/dev/null || true
wait

exit "$EXIT_CODE"
