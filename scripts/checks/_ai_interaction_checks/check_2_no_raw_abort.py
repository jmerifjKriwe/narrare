"""Check 2 — No raw AbortController in feature code (ADR-043).

Scans all TypeScript files in the web package for ``new AbortController``
and classifies each occurrence:

- **ALLOWED**: central primitives (useAIOperation, ai-operation-execute),
  transport layer (streaming.ts / connectSSE), test infrastructure
  (``__tests__/``, ``*.test.*``, ``ai-test-helpers.ts``).
- **VIOLATION**: local AI-feature flows in React components or hooks
  that manage their own AbortController instead of using useAIOperation.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from ._shared import WEB_DIR, ExcludeRegistry, display_path, rg_lines

GATE = "check_2_no_raw_abort"

# ---------------------------------------------------------------------------
# Allowed-path classification
# ---------------------------------------------------------------------------

# Regex patterns matched against the repo-relative path (posix).
# Any match → the file is a central primitive / test infrastructure.
_ALLOWED_PATTERNS: list[re.Pattern[str]] = [
    # Central primitives — useAIOperation internals
    re.compile(r"lib/hooks/ai-operation-execute\.ts$"),
    re.compile(r"lib/hooks/use-ai-operation\.ts$"),
    re.compile(r"lib/hooks/use-ai-operation\.types\.ts$"),
    # Transport layer — connectSSE
    re.compile(r"lib/api/streaming\.ts$"),
    # Test infrastructure
    re.compile(r"/__tests__/"),
    re.compile(r"\.test\.(ts|tsx)$"),
    re.compile(r"ai-test-helpers\.ts$"),
]


def _is_allowed_path(rel_path: str) -> bool:
    """Return True if *rel_path* is a known central / test file."""
    return any(p.search(rel_path) for p in _ALLOWED_PATTERNS)


# ---------------------------------------------------------------------------
# Scan helpers
# ---------------------------------------------------------------------------

_STUDIO_DIR = WEB_DIR / "components" / "studio"
_HOOKS_DIR = WEB_DIR / "lib" / "hooks"


def _find_abort_controller_files() -> list[Path]:
    """Find all TS/TSX files containing ``new AbortController``."""
    found: set[Path] = set()
    for scan_dir in (_STUDIO_DIR, _HOOKS_DIR):
        if not scan_dir.exists():
            continue
        for ext in ("*.ts", "*.tsx"):
            for fp in scan_dir.rglob(ext):
                try:
                    content = fp.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if "new AbortController" in content:
                    found.add(fp)
    return sorted(found)


# ---------------------------------------------------------------------------
# Public check function
# ---------------------------------------------------------------------------


def check_no_raw_abort_controller(
    registry: ExcludeRegistry,
) -> tuple[list[str], list[str]]:
    passes: list[str] = []
    violations: list[str] = []

    if not _STUDIO_DIR.exists() and not _HOOKS_DIR.exists():
        passes.append("Studio/hooks directories not found -- skip")
        return passes, violations

    files = _find_abort_controller_files()
    if not files:
        passes.append("No raw AbortController in feature code +")
        return passes, violations

    for fp in files:
        rel = display_path(fp)

        # Central primitives / test infrastructure are always allowed.
        if _is_allowed_path(rel):
            passes.append(f"{rel} — central primitive / test infrastructure (allowed)")
            continue

        # Governed exclusion — skip silently (reported as debt by main checker).
        if registry.is_excluded(rel, gate=GATE):
            continue

        # Violation — local feature code with own Abort logic.
        detail_lines = rg_lines(r"new AbortController", str(fp))
        detail = ""
        if detail_lines:
            shown: list[str] = []
            for line in detail_lines:
                if len(shown) >= 3:
                    break
                parts = line.split(":", 1)
                if len(parts) == 2:
                    shown.append(f"    L{parts[0]}: {parts[1].strip()[:100]}")
            if shown:
                detail = "\n" + "\n".join(shown)

        violations.append(
            f"{rel} uses raw AbortController instead of useAIOperation{detail}\n"
            f"  -> Use useAIOperation hook for AI lifecycle management\n"
            f"  -> Or add to exclude list with reason and exit criterion"
        )

    return passes, violations
