#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/run_vrt.sh — Run Playwright VRT screenshot tests
#
# Portable wrapper around `playwright test --project=vrt` that performs two
# preflight checks and then hands off to Playwright:
#
#   1. Browser system dependencies — verifies the Chromium runtime libraries
#      are resolvable (via ldconfig cache OR LD_LIBRARY_PATH). On Linux a
#      missing libcups/libnss/etc. causes Chromium to fail to launch AFTER
#      the expensive Next.js dev-server cold compile — this check fails fast.
#   2. Port 3000 free — Playwright's webServer uses `reuseExistingServer: true`
#      (see packages/web/playwright.config.ts). A stale or broken server
#      already bound to :3000 is silently reused, producing false/duplicated
#      baselines. We refuse to run and point at the offending PID instead.
#      We NEVER auto-kill — that could target an unrelated production server.
#
# Usage:
#   scripts/run_vrt.sh                 # run VRT, fail on diff (default)
#   scripts/run_vrt.sh --update        # regenerate baselines (--update-snapshots)
#   VRT_PORT=3000 scripts/run_vrt.sh   # override the port to check (default 3000)
#   PTIMEOUT=1800000 scripts/run_vrt.sh  # override Playwright per-test timeout (ms)
#
# Exit codes:
#   0              success (tests pass, or baselines updated)
#   1              preflight failure (missing deps, port in use, bad args)
#   other          forwarded from Playwright
#
# See:
#   - docs/architecture/decisions/ADR-059-vrt-and-design-system-strategy.md
#   - packages/web/tests/screenshots/  (determinism contract per spec)
#
# CI runs the same project directly (`pnpm playwright test --project=vrt`)
# on a clean runner — the preflight checks here exist for LOCAL dev machines
# only and are intentionally non-fatal when the host cannot be inspected.
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_DIR="$REPO_ROOT/packages/web"
VRT_PORT="${VRT_PORT:-3000}"

# ── argument parsing ────────────────────────────────────────────────────────

PW_ARGS=(--project=vrt)
case "${1:-}" in
  ""|--update|--update-snapshots)
    [ "${1:-}" != "" ] && PW_ARGS+=(--update-snapshots)
    ;;
  *)
    echo "ERROR: unknown argument: $1" >&2
    echo "Usage: $0 [--update]" >&2
    exit 1
    ;;
esac

# Per-test timeout override (ms). Only passed when explicitly set so the
# playwright.config.ts default is honoured otherwise.
if [ -n "${PTIMEOUT:-}" ]; then
  PW_ARGS+=(--timeout="$PTIMEOUT")
fi

# ── preflight 1: Chromium system dependencies (Linux only) ──────────────────
# macOS / Windows bundle their own browser via Playwright; the shared-library
# model is Linux-specific.

lib_available() {
  # A library is "available" if it is in the ldconfig cache OR exists in an
  # LD_LIBRARY_PATH directory. Checking LD_LIBRARY_PATH (not just ldconfig)
  # is portable and correct — it is the standard override mechanism, not a
  # machine-specific workaround.
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
  if [ "$(uname -s)" != "Linux" ]; then
    return 0
  fi
  local required=(
    libcups.so.2 libnss3.so libnssutil3.so libnspr4.so
    libatk-1.0.so.0 libatk-bridge-2.0.so.0
    libgbm.so.1 libdrm.so.2
    libxkbcommon.so.0 libpango-1.0.so.0 libcairo.so.2
    libasound.so.2
  )
  local missing=()
  local lib
  for lib in "${required[@]}"; do
    lib_available "$lib" || missing+=("$lib")
  done
  if [ "${#missing[@]}" -gt 0 ]; then
    cat >&2 <<EOF
❌ Playwright Chromium system dependencies appear to be missing:

$(printf '     - %s\n' "${missing[@]}")

   Install them with the canonical, distro-aware Playwright command:

     sudo npx playwright install-deps chromium

   …or manually on Debian/Ubuntu (package names vary by release; e.g.
   libcups2 vs libcups2t64):

     sudo apt-get install -y libcups2 libnss3 libnspr4 libatk1.0-0 \
         libatk-bridge2.0-0 libgbm1 libdrm2 libxkbcommon0 libpango-1.0-0 \
         libcairo2 libasound2

   Then re-run: just vrt
EOF
    return 1
  fi
}

# ── preflight 2: is $VRT_PORT already listening? ────────────────────────────

port_listening() {
  # Returns 0 (true) if something is LISTENing on $VRT_PORT.
  local hex
  hex="$(printf '%04X' "$VRT_PORT")"
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
  # Fallbacks for non-Linux or restricted /proc
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | grep -qE "[:.]${VRT_PORT}\b" && return 0 || return 1
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$VRT_PORT" -sTCP:LISTEN -P -n 2>/dev/null | tail -n +2 | grep -q . && return 0 || return 1
  fi
  echo "⚠️  Cannot inspect listening sockets (no /proc/net, ss, or lsof)." >&2
  echo "    Assuming port $VRT_PORT is free. If Playwright reuses a stale server," >&2
  echo "    snapshots may be wrong — kill any leftover 'next dev' and re-run." >&2
  return 1
}

resolve_port_pid() {
  # Best-effort PID resolution for a helpful hint. Empty string if unknown.
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null \
      | grep -E "[:.]${VRT_PORT}\b" \
      | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2
    return
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$VRT_PORT" -sTCP:LISTEN -P -n -t 2>/dev/null | head -1
    return
  fi
}

check_port_free() {
  if port_listening; then
    local pid; pid="$(resolve_port_pid || true)"
    cat >&2 <<EOF
❌ Port $VRT_PORT is already in use.

   Playwright's webServer is configured with \`reuseExistingServer: true\`
   (packages/web/playwright.config.ts), so it will silently attach to the
   existing server. If that server is stale, broken, or a different build,
   the VRT baselines will be wrong (false passes or spurious diffs).

EOF
    if [ -n "$pid" ]; then
      echo "   Likely owner: PID $pid" >&2
      echo "   Stop it, e.g.:  kill $pid   (then re-run: just vrt)" >&2
    else
      echo "   Could not resolve the owning PID automatically." >&2
      echo "   Find it with:  ss -ltnp 'sport = :$VRT_PORT'  or  lsof -iTCP:$VRT_PORT" >&2
    fi
    echo "" >&2
    echo "   (This script intentionally does NOT auto-kill — that could" >&2
    echo "    target an unrelated production server.)" >&2
    return 1
  fi
}

# ── run preflight, then Playwright ──────────────────────────────────────────

check_browser_deps
check_port_free

if [ "${#PW_ARGS[@]}" -gt 1 ] && [ "${PW_ARGS[1]}" = "--update-snapshots" ]; then
  echo "🖼️  Running VRT with --update-snapshots (regenerating baselines)…"
else
  echo "🖼️  Running VRT screenshot tests…"
fi
echo "    project: vrt   port: $VRT_PORT   workdir: packages/web"
echo ""

cd "$WEB_DIR"
exec pnpm exec playwright test "${PW_ARGS[@]}"
