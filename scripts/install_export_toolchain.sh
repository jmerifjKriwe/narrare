#!/bin/sh
# ============================================================================
# Narrare Export Toolchain Installer (ADR-081 / IO-001)
# ============================================================================
#
# Idempotent, POSIX-sh installer for the manuscript-export render binaries.
# Single source of truth for the exact version pins (D4 — newest stable,
# locked at IO-001 Slice 0). Two consumers:
#
#   1. Dockerfile release runtime stage (Typst + pandoc, no EPUBCheck).
#   2. CI integration/e2e jobs (Typst + pandoc + EPUBCheck).
#
# Override the pins via env vars for bump-testing, e.g.:
#   TYPST_VERSION=0.14.0 bash scripts/install_export_toolchain.sh
#
# EPUBCheck is CI-only: pass INSTALL_EPUBCHECK=1 to install it. It is never
# in the release image (PDF/EPUB/MD don't need it at runtime; only CI
# validates rendered EPUBs).
#
# Install prefix:
#   NARRARE_TOOLCHAIN_DIR set → that dir's {bin,share} (CI cache target;
#     caller MUST put "$NARRARE_TOOLCHAIN_DIR/bin" on PATH)
#   otherwise root      → /usr/local/{bin,share}
#   otherwise non-root  → ~/.local/{bin,share}   (ensure it is on $PATH)
#
# Requirements: curl, tar (any), python3 (used for portable extraction of
# .tar.xz / .tar.gz / .zip so the script needs no xz-utils / unzip).
# EPUBCheck additionally requires a Java runtime (java) at invocation time.
#
# Usage:
#   bash scripts/install_export_toolchain.sh                 # Typst + pandoc
#   INSTALL_EPUBCHECK=1 bash scripts/install_export_toolchain.sh   # + EPUBCheck
# ============================================================================
set -eu

# ---------------------------------------------------------------------------
# Version pins (D4 — newest stable at IO-001 Slice 0, 2026-08-10)
# ---------------------------------------------------------------------------
# GitHub release tags: Typst and EPUBCheck are "v"-prefixed; pandoc is not.
TYPST_VERSION="${TYPST_VERSION:-0.15.1}"
PANDOC_VERSION="${PANDOC_VERSION:-3.10.1}"
EPUBCHECK_VERSION="${EPUBCHECK_VERSION:-5.3.0}"

# Target binaries confined by RULE-08 — see
# apps/api/narrare/export/renderers/ (the only allowed spawn sites).
INSTALL_EPUBCHECK="${INSTALL_EPUBCHECK:-0}"

# ---------------------------------------------------------------------------
# Install prefix (NARRARE_TOOLCHAIN_DIR override → root → /usr/local → ~/.local)
# ---------------------------------------------------------------------------
if [ -n "${NARRARE_TOOLCHAIN_DIR:-}" ]; then
    # Explicit target dir (CI cache, W3-3). Every tool below installs
    # under this one prefix: typst + pandoc + the epubcheck launcher →
    # $PREFIX/bin, the EPUBCheck jar tree → $PREFIX/share/epubcheck
    # (launcher resolves lib/ relative to the jar). Unset → unchanged
    # defaults (local parity, Docker root install).
    PREFIX="${NARRARE_TOOLCHAIN_DIR}"
elif [ "$(id -u)" -eq 0 ]; then
    PREFIX="/usr/local"
else
    PREFIX="${HOME}/.local"
fi
BINDIR="${PREFIX}/bin"
SHAREDIR="${PREFIX}/share"
mkdir -p "$BINDIR" "$SHAREDIR"

# Portable temp dir (cleaned on exit).
TMPDIR="$(mktemp -d)"
cleanup() {
    rm -rf "$TMPDIR"
}
trap cleanup EXIT HUP INT TERM

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() {
    printf '==> %s\n' "$*"
}

download() {
    # download <url> <dest>
    url="$1"
    dest="$2"
    log "Downloading $url"
    curl -fsSL --retry 3 -o "$dest" "$url"
}

# Extract any archive with Python (no xz-utils/unzip dependency).
# extract <archive> <dest_dir> <mode>   mode ∈ {xz, gz, zip}
extract() {
    archive="$1"
    dest="$2"
    mode="$3"
    mkdir -p "$dest"
    python3 - "$archive" "$dest" "$mode" <<'PY'
import sys, tarfile, zipfile
archive, dest, mode = sys.argv[1], sys.argv[2], sys.argv[3]
if mode == "zip":
    with zipfile.ZipFile(archive) as z:
        z.extractall(dest)
else:
    with tarfile.open(archive, f"r:{mode}") as t:
        t.extractall(dest)
PY
}

# ---------------------------------------------------------------------------
# Typst (static musl binary — RULE-08: only renderers/typst.py may invoke it)
# ---------------------------------------------------------------------------
install_typst() {
    log "Installing Typst ${TYPST_VERSION}"
    archive="$TMPDIR/typst.tar.xz"
    download \
        "https://github.com/typst/typst/releases/download/v${TYPST_VERSION}/typst-x86_64-unknown-linux-musl.tar.xz" \
        "$archive"
    extract "$archive" "$TMPDIR/typst-extract" xz
    # tarball layout: typst-x86_64-unknown-linux-musl/typst
    bin="$TMPDIR/typst-extract/typst-x86_64-unknown-linux-musl/typst"
    if [ ! -f "$bin" ]; then
        echo "ERROR: typst binary not found in archive" >&2
        exit 1
    fi
    install -m 0755 "$bin" "$BINDIR/typst"
}

# ---------------------------------------------------------------------------
# pandoc (prebuilt linux-amd64 tarball — RULE-08: only renderers/pandoc_*.py)
# ---------------------------------------------------------------------------
install_pandoc() {
    log "Installing pandoc ${PANDOC_VERSION}"
    archive="$TMPDIR/pandoc.tar.gz"
    download \
        "https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/pandoc-${PANDOC_VERSION}-linux-amd64.tar.gz" \
        "$archive"
    extract "$archive" "$TMPDIR/pandoc-extract" gz
    # tarball layout: pandoc-<ver>/bin/pandoc
    bin="$TMPDIR/pandoc-extract/pandoc-${PANDOC_VERSION}/bin/pandoc"
    if [ ! -f "$bin" ]; then
        echo "ERROR: pandoc binary not found in archive" >&2
        exit 1
    fi
    install -m 0755 "$bin" "$BINDIR/pandoc"
}

# ---------------------------------------------------------------------------
# EPUBCheck (CI-only — NOT a production render binary; invoked from the
# tests/golden/export/ harness, so it is deliberately OUTSIDE RULE-08 scope).
# Installs a `epubcheck` launcher that execs `java -jar`.
# ---------------------------------------------------------------------------
install_epubcheck() {
    log "Installing EPUBCheck ${EPUBCHECK_VERSION} (CI-only)"
    # EPUBCheck is a Java tool — warn (do not fail) if java is absent; the
    # launcher will report the real error at invocation time.
    if ! command -v java >/dev/null 2>&1; then
        echo "WARNING: java not found on PATH — EPUBCheck needs a Java runtime." >&2
    fi
    archive="$TMPDIR/epubcheck.zip"
    download \
        "https://github.com/w3c/epubcheck/releases/download/v${EPUBCHECK_VERSION}/epubcheck-${EPUBCHECK_VERSION}.zip" \
        "$archive"
    extract "$archive" "$TMPDIR/epubcheck-extract" zip
    # zip layout: epubcheck-<ver>/{epubcheck.jar,lib/}
    src="$TMPDIR/epubcheck-extract/epubcheck-${EPUBCHECK_VERSION}"
    if [ ! -f "$src/epubcheck.jar" ]; then
        echo "ERROR: epubcheck.jar not found in archive" >&2
        exit 1
    fi
    # Install to a version-stable path so the launcher never hardcodes a version.
    dest="$SHAREDIR/epubcheck"
    rm -rf "$dest"
    cp -r "$src" "$dest"
    # Launcher script — manifest Class-Path resolves lib/ relative to the jar.
    launcher="$BINDIR/epubcheck"
    cat > "$launcher" <<EOF
#!/bin/sh
# EPUBCheck launcher (generated by scripts/install_export_toolchain.sh)
# CI-only validation tool (ADR-081). Not a production render binary.
exec java -jar "$dest/epubcheck.jar" "\$@"
EOF
    chmod 0755 "$launcher"
}

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
install_typst
install_pandoc
if [ "$INSTALL_EPUBCHECK" = "1" ]; then
    install_epubcheck
else
    log "Skipping EPUBCheck (set INSTALL_EPUBCHECK=1 to install, CI-only)"
fi

log "Export toolchain installed to ${BINDIR}"
# Version sanity check — fails the script if a binary is broken/missing.
# Use the absolute BINDIR path so this works even when BINDIR is not on $PATH
# (e.g. ~/.local/bin inside a fresh Docker layer).
"$BINDIR/typst" --version
"$BINDIR/pandoc" --version | head -1
if [ "$INSTALL_EPUBCHECK" = "1" ]; then
    "$BINDIR/epubcheck" --version 2>&1 | head -1 || true
fi
