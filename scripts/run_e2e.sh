#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/run_e2e.sh — Run the canonical Python pytest-playwright E2E suite
#                      locally, CI-faithfully.
#
# Problem this solves:
#   The existing `just test-e2e` recipe runs only `pytest ... --timeout=60`
#   and assumes the developer has already started the full stack in E2E mode.
#   The CI job (`.github/workflows/ci.yml` → `test-e2e`, runs only on `main`)
#   does much more: brings up services, sets `ENVIRONMENT=test` (which flips
#   `is_test=True` → CSRF disabled), uses the `narrare_test` DB, runs
#   `pnpm build` + standalone Next.js, and uses `--timeout=300`.
#
#   The local/CI env mismatch (CSRF active vs. inactive) is the single most
#   common cause of "passes locally, fails in CI" for E2E. This wrapper
#   closes that gap.
#
# What it does (in order):
#   1. Preflight — docker services up (:5433, :6379), app ports free
#      (:3000, :8000), Playwright Chromium libs present. Exits with a clear
#      remediation hint if any check fails. NEVER auto-starts docker or
#      auto-kills stray processes — both are user decisions.
#   2. DB setup — `alembic upgrade head` + `seed_dev_user.py` against the
#      `narrare_test` DB on :5433 (NOT the dev DB on :5432).
#   3. Start services in CI-faithful env (ENVIRONMENT=test, NARRARE_E2E_TEST=1,
#      TestModel for all LLM providers). API on :8000, frontend on :3000.
#   4. Readiness-wait — poll /health and / until both respond (≤60s/90s).
#   5. Run pytest with CI's timeout (`--timeout=300 --timeout-method=thread`).
#   6. Cleanup trap (EXIT/INT/TERM) — kills both services via process-group
#      SIGTERM, escalating to SIGKILL if needed. No service leaks.
#
# Frontend mode:
#   E2E_FRONTEND_MODE=dev   (default) — `pnpm dev` (fast startup, HMR).
#   E2E_FRONTEND_MODE=build           — `pnpm build` + standalone node server
#                                       (CI-faithful; use if dev-mode masks a
#                                       production-only failure).
#
# Usage:
#   just e2e                              # canonical entry point
#   scripts/run_e2e.sh                    # direct
#   E2E_FRONTEND_MODE=build just e2e      # CI-exact frontend path
#   HEADED=true just e2e                  # run browser headed (debug)
#
# Exit codes:
#   0              success (pytest passed)
#   1              preflight failure, service startup failure, or pytest
#                  reported a non-zero exit that the script normalized to 1
#   other          forwarded from pytest as-is
#
# References:
#   - CI job:        .github/workflows/ci.yml (test-e2e, ~L718-862)
#   - Test layout:   tests/e2e/  (see tests/AGENTS.md)
#   - Sister script: scripts/run_vrt.sh (same preflight philosophy, no services)
#   - docker-compose.dev.yml defines `postgres_test` on :5433 (tmpfs)
#
# Permission model: this script is invoked via `just e2e` (matches the
# allowed `just*` pattern). Internal commands (uv, pnpm, node, curl, cat)
# run inside the bash subprocess without further permission gates.
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"
WEB_DIR="$REPO_ROOT/packages/web"
LOG_DIR="$REPO_ROOT/logs"

# ---------------------------------------------------------------------------
# CI-faithful environment (mirrors .github/workflows/ci.yml → test-e2e.env).
#
# PORT DIFFERENCE: CI maps postgres to :5432 (the runner has no dev DB).
# Locally, :5432 is the dev DB; the test DB lives on :5433 via
# docker-compose.dev.yml → postgres_test (tmpfs). The DB NAME matches CI
# (narrare_test), only the port differs.
# ---------------------------------------------------------------------------
TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test}"
export DATABASE_URL="$TEST_DATABASE_URL"
export TEST_DATABASE_URL
export ENVIRONMENT=test                       # → is_test=True → CSRF disabled (the core CI-faithfulness lever)
export SECRET_KEY=test-secret-key-not-for-production
export NARRARE_E2E_TEST=1                     # → all LLM factories return pydantic_ai.TestModel
export ANTHROPIC_API_KEY=sk-test-dummy        # required by settings validation; unused under NARRARE_E2E_TEST
export OPENAI_API_KEY=sk-test-dummy
export NARRARE_ENCRYPTION_KEY=WYcr1iULJse2Oo6GPpmw1Au4ovp_fXZwbrNF11C12ZQ=
export AUTH_JWT_SECRET=test-secret-key-not-for-production   # must match backend SECRET_KEY for JWT verify
export NEXT_PUBLIC_API_URL=http://localhost:8000
export E2E_BASE_URL=http://localhost:3000
export E2E_API_URL=http://localhost:8000
export CI=true                               # matches pytest-e2e step env; some conftest branches on this

E2E_FRONTEND_MODE="${E2E_FRONTEND_MODE:-dev}"

PG_TEST_PORT=5433
API_PORT=8000
WEB_PORT=3000

# PIDs of the session leaders (= PGIDs after setsid). Empty until assigned.
API_PID=""
WEB_PID=""
_CLEANING_UP=0

# ---------------------------------------------------------------------------
# logging
# ---------------------------------------------------------------------------
log()  { printf '\033[1;34m[e2e]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[e2e]\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[e2e ERROR]\033[0m %s\n' "$*" >&2; }

# ---------------------------------------------------------------------------
# port helpers (same logic as scripts/run_vrt.sh)
# ---------------------------------------------------------------------------
port_listening() {
  # 0 (true) if something is LISTENing on $1
  local port="$1" hex
  hex="$(printf '%04X' "$port")"
  if [ -r /proc/net/tcp ] || [ -r /proc/net/tcp6 ]; then
    local f
    for f in /proc/net/tcp /proc/net/tcp6; do
      [ -r "$f" ] || continue
      # col 2 = local_address (IP:PORT), col 4 = st (0A = LISTEN)
      if awk -v p=":$hex" 'NR>1 && index($2,p)>0 && $4=="0A" {f=1} END{exit !f}' "$f"; then
        return 0
      fi
    done
    return 1
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | grep -qE "[:.]${port}\b" && return 0 || return 1
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN -P -n 2>/dev/null | tail -n +2 | grep -q . && return 0 || return 1
  fi
  return 1
}

resolve_port_pid() {
  # Best-effort PID resolution for a helpful hint. Empty string if unknown.
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null \
      | grep -E "[:.]${port}\b" \
      | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2
    return
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN -P -n -t 2>/dev/null | head -1
    return
  fi
}

# ---------------------------------------------------------------------------
# browser-deps preflight (copied from scripts/run_vrt.sh — same Chromium libs)
# ---------------------------------------------------------------------------
lib_available() {
  local lib="$1"
  if command -v ldconfig >/dev/null 2>&1 && ldconfig -p 2>/dev/null | grep -qF "$lib"; then
    return 0
  fi
  local oldIFS="$IFS"
  IFS=":"
  set -f
  local dir
  for dir in ${LD_LIBRARY_PATH:-}; do
    [ -n "$dir" ] && [ -e "$dir/$lib" ] && { IFS="$oldIFS"; set +f; return 0; }
  done
  IFS="$oldIFS"
  set +f
  return 1
}

check_browser_deps() {
  # macOS/Windows bundle their own browser via Playwright. Shared-lib model
  # is Linux-specific. E2E uses the same Chromium that VRT does.
  [ "$(uname -s)" = "Linux" ] || return 0
  local required=(
    libcups.so.2 libnss3.so libnssutil3.so libnspr4.so
    libatk-1.0.so.0 libatk-bridge-2.0.so.0
    libgbm.so.1 libdrm.so.2
    libxkbcommon.so.0 libpango-1.0.so.0 libcairo.so.2
    libasound.so.2
  )
  local missing=() lib
  for lib in "${required[@]}"; do
    lib_available "$lib" || missing+=("$lib")
  done
  if [ "${#missing[@]}" -gt 0 ]; then
    err "Playwright Chromium system dependencies appear to be missing:"
    printf '     - %s\n' "${missing[@]}" >&2
    cat >&2 <<EOF

   Install with:  sudo npx playwright install-deps chromium
   Then re-run:   just e2e
EOF
    return 1
  fi
}

# ---------------------------------------------------------------------------
# preflight: docker services up + app ports free
# ---------------------------------------------------------------------------
preflight_services() {
  # :5433 must be LISTENing. If not: tell the user how to start it.
  # We do NOT auto-start docker — that is a user/environment decision
  # (and `docker compose` is outside this agent's bash permission set).
  local missing=()
  port_listening "$PG_TEST_PORT" || missing+=("$PG_TEST_PORT (postgres_test)")
  if [ "${#missing[@]}" -gt 0 ]; then
    err "Required Docker services are not listening:"
    for m in "${missing[@]}"; do echo "    - port $m" >&2; done
    cat >&2 <<EOF

   Start it (the test DB lives on :5433, NOT the dev DB on :5432):

     docker compose -f docker-compose.dev.yml up -d postgres_test

   Then re-run:  just e2e
EOF
    return 1
  fi
  log "  docker services reachable: postgres_test :$PG_TEST_PORT"
}

preflight_ports_free() {
  # :3000 and :8000 must be FREE (we will start api+frontend on them).
  # A stale server on these ports would conflict and produce confusing errors.
  # We do NOT auto-kill — see scripts/run_vrt.sh for the same policy.
  local bad=0 p
  for p in "$API_PORT" "$WEB_PORT"; do
    if port_listening "$p"; then
      local pid; pid="$(resolve_port_pid "$p" || true)"
      err "Port :$p is already in use."
      if [ -n "$pid" ]; then
        echo "    Likely owner: PID $pid — stop with:  kill $pid" >&2
      else
        echo "    Owner unknown — find via:  ss -ltnp 'sport = :$p'  or  lsof -iTCP:$p" >&2
      fi
      bad=1
    fi
  done
  if [ "$bad" -ne 0 ]; then
    echo "" >&2
    echo "    (Script intentionally does NOT auto-kill — that could target" >&2
    echo "     an unrelated production server.)" >&2
    return 1
  fi
  log "  app ports free: :$API_PORT, :$WEB_PORT"
}

# ---------------------------------------------------------------------------
# cleanup — kill both service process groups. Runs on EXIT/INT/TERM/HUP,
# regardless of pytest outcome. This is the single most important guarantee:
# no leaked uvicorn/next-dev processes after the run (the VM has been blocked
# by exactly such leaks in the past).
# ---------------------------------------------------------------------------
cleanup() {
  [ "$_CLEANING_UP" -eq 1 ] && return 0
  _CLEANING_UP=1
  # De-arm traps so we cannot re-enter on a double signal.
  trap - EXIT INT TERM HUP

  echo ""
  log "⏹  Cleaning up services…"
  local pid
  for pid in "$API_PID" "$WEB_PID"; do
    [ -n "$pid" ] || continue
    if kill -0 "$pid" 2>/dev/null; then
      # Negative PID = process group (setsid made the child a session leader,
      # so PGID == PID). Reaches uvicorn workers, next-dev child processes, etc.
      kill -TERM "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
      # Give it up to ~3s to exit gracefully.
      local i
      for i in $(seq 1 10); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.3
      done
      if kill -0 "$pid" 2>/dev/null; then
        warn "PID $pid did not exit on SIGTERM — sending SIGKILL"
        kill -KILL "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
      fi
    fi
  done
  wait 2>/dev/null || true
  log "✓ Cleanup complete"
}

trap cleanup EXIT INT TERM HUP

# ---------------------------------------------------------------------------
# readiness-wait — accept any 2xx/3xx (Next.js dev redirects / → /en)
# ---------------------------------------------------------------------------
wait_for_http_any() {
  local url="$1" name="$2" max="$3" i code
  for i in $(seq 1 "$max"); do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "$url" 2>/dev/null || echo "000")"
    case "$code" in
      2*|3*) log "  $name ready (HTTP $code after ${i}s)"; return 0 ;;
    esac
    sleep 1
  done
  err "$name did not become ready within ${max}s (last HTTP status: $code)"
  return 1
}

# ===========================================================================
# main flow
# ===========================================================================
mkdir -p "$LOG_DIR"

log "Preflight checks"
log "  frontend mode: $E2E_FRONTEND_MODE  (override with E2E_FRONTEND_MODE=build|dev)"
preflight_services
preflight_ports_free
check_browser_deps

log "Database: alembic upgrade head  (DB: narrare_test on :$PG_TEST_PORT)"
( cd "$API_DIR" && uv run alembic upgrade head )

log "Database: seed dev user  (idempotent; dev@narrare.dev / narrare-dev)"
( cd "$REPO_ROOT" && uv run python scripts/seed_dev_user.py )

# ---------------------------------------------------------------------------
# start API (background, new session → PGID == PID for group-kill)
# ---------------------------------------------------------------------------
log "Starting API server on :$API_PORT  (ENVIRONMENT=test, NARRARE_E2E_TEST=1 → TestModel)"
# `setsid bash -c "… exec …"`: bash forks → child execs setsid → setsid(2) creates
# a new session → exec bash -c → inner bash execs uv. Final PID == $!, and it is
# the session leader, so `kill -- -$!` reaches the whole tree.
setsid bash -c "cd '$API_DIR' && exec uv run uvicorn narrare._app.main:app \
    --host 0.0.0.0 --port $API_PORT" \
  > "$LOG_DIR/e2e-api.log" 2>&1 &
API_PID=$!
log "  API PID: $API_PID  (log: $LOG_DIR/e2e-api.log)"

# ---------------------------------------------------------------------------
# start frontend (dev or build). Build mode replicates CI's standalone flow.
# ---------------------------------------------------------------------------
if [ "$E2E_FRONTEND_MODE" = "build" ]; then
  log "Frontend: pnpm build  (CI-faithful standalone)"
  ( cd "$WEB_DIR" && pnpm build )
  # Replicate CI's standalone-layout fixups (next.config.ts: output: "standalone")
  cp -r "$WEB_DIR/.next/static" "$WEB_DIR/.next/standalone/packages/web/.next/static"
  cp -r "$WEB_DIR/public"       "$WEB_DIR/.next/standalone/packages/web/public"
  log "Starting standalone Next.js server on :$WEB_PORT"
  setsid bash -c "cd '$WEB_DIR' && exec env PORT=$WEB_PORT \
      node .next/standalone/packages/web/server.js" \
    > "$LOG_DIR/e2e-frontend.log" 2>&1 &
  WEB_PID=$!
else
  # Ensure .env.local exists (justfile's dev-frontend does the same). Our
  # exported AUTH_JWT_SECRET / NEXT_PUBLIC_API_URL take precedence over
  # anything in .env.local because Next.js reads process.env first.
  [ -f "$WEB_DIR/.env.local" ] || cp "$WEB_DIR/.env.local.example" "$WEB_DIR/.env.local"
  log "Starting Next.js dev server on :$WEB_PORT  (HMR; set E2E_FRONTEND_MODE=build for CI-exact)"
  setsid bash -c "cd '$WEB_DIR' && exec pnpm dev" \
    > "$LOG_DIR/e2e-frontend.log" 2>&1 &
  WEB_PID=$!
fi
log "  Frontend PID: $WEB_PID  (log: $LOG_DIR/e2e-frontend.log)"

# ---------------------------------------------------------------------------
# readiness
# ---------------------------------------------------------------------------
log "Waiting for services to become ready…"
if ! wait_for_http_any "http://localhost:$API_PORT/health" "API" 60; then
  err "API log tail:"
  tail -n 50 "$LOG_DIR/e2e-api.log" >&2 || true
  exit 1
fi
if ! wait_for_http_any "http://localhost:$WEB_PORT/" "Frontend" 90; then
  err "Frontend log tail:"
  tail -n 50 "$LOG_DIR/e2e-frontend.log" >&2 || true
  exit 1
fi

# ---------------------------------------------------------------------------
# run E2E tests — CI's exact invocation (timeout 300s, thread method)
# ---------------------------------------------------------------------------
log "Running E2E tests: pytest tests/e2e/ -v -m e2e --timeout=300 --timeout-method=thread"
echo ""
# Temporarily disable `set -e` so pytest's exit code is captured, not swallowed.
set +e
( cd "$REPO_ROOT" && uv run pytest tests/e2e/ -v -m e2e --timeout=300 --timeout-method=thread )
PYTEST_RC=$?
set -e
echo ""

if [ "$PYTEST_RC" -eq 0 ]; then
  log "✅ E2E tests passed"
else
  err "❌ E2E tests failed (pytest exit $PYTEST_RC)"
  echo "    Logs:  $LOG_DIR/e2e-api.log  |  $LOG_DIR/e2e-frontend.log" >&2
fi

exit "$PYTEST_RC"
