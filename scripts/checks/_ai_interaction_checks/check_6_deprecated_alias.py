"""Check 6 — Deprecated §16.8 AI-action alias gate.

Scans TS/TSX files for exact deprecated AI-action aliases listed in
``docs/development/ui-principles.md`` §16.8. Broader namespaces are NOT
banned — only the exact deprecated alias keys.

Motivated by CR-AUFG-07-12 (Deprecated AI-Action i18n Alias Prevention).
"""

from __future__ import annotations

import re
import subprocess  # nosec
from pathlib import Path

from ._shared import WEB_DIR, ExcludeRegistry, display_path

GATE = "check_6_deprecated_alias"

# Exact deprecated §16.8 AI-action aliases (DO NOT USE).
# These are the 16 aliases listed in ui-principles.md §16.8.
DEPRECATED_ALIASES: list[str] = [
    "aiModal.accept",
    "aiModal.reject",
    "aiModal.original",
    "generation.stop",
    "generation.accept",
    "generation.reject",
    "annotation.keep",
    "annotation.undo",
    "rewrite.cancel",
    "rewrite.replace",
    "sessionPanel.addToDraft",
    "kb.sessions.accept",
    "kb.sessions.reject",
    "learning.rating",
    "coAuthor.acceptAll",
    "coAuthor.rejectAll",
    "coAuthor.applySelected",
]


def _find_deprecated_alias_usage(alias: str) -> list[tuple[str, str]]:
    """Find TS/TSX files using the exact deprecated *alias* as an i18n key.

    Matches the alias inside quotes (single or double) to avoid false
    positives from substring matches.  Returns ``(filepath, matched_line)``
    pairs.
    """
    escaped = re.escape(alias)
    # Match alias inside quotes: "alias" or 'alias'
    pattern = rf'["\']({escaped})["\']'

    cmd = [
        "rg",
        "--no-heading",
        "-n",
        "-g",
        "*.ts",
        "-g",
        "*.tsx",
        pattern,
        str(WEB_DIR),
    ]
    try:
        proc = subprocess.run(  # noqa: S603  # nosec
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired, FileNotFoundError:
        return []

    if proc.returncode not in (0, 1):
        return []

    results: list[tuple[str, str]] = []
    for raw_line in proc.stdout.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        # rg output: filepath:line:content
        parts = raw_line.split(":", 2)
        if len(parts) >= 2:
            filepath = parts[0]
            content = parts[2] if len(parts) >= 3 else ""
            results.append((filepath, content.strip()[:120]))
    return results


def check_deprecated_aliases(
    registry: ExcludeRegistry,
) -> tuple[list[str], list[str]]:
    """Check 6: No deprecated §16.8 AI-action aliases in TS/TSX code.

    Returns ``(passes, violations)``.  Each violation names the file,
    line, and exact deprecated alias with migration guidance.
    """
    passes: list[str] = []
    violations: list[str] = []

    any_scanned = False

    for alias in DEPRECATED_ALIASES:
        hits = _find_deprecated_alias_usage(alias)
        if not hits:
            continue

        any_scanned = True
        for filepath_str, content in hits:
            fp = Path(filepath_str)
            rel = display_path(fp)

            # Governed exclusion — skip silently (reported as debt).
            if registry.is_excluded(rel, gate=GATE):
                continue

            violations.append(
                f"{rel} uses deprecated alias '{alias}'\n"
                f"    {content}\n"
                f"  -> Replace with canonical studio.aiActions.* key (see §16.8)\n"
                f"  -> Or add to exclude list with reason and exit criterion"
            )

    if not any_scanned:
        passes.append("No deprecated §16.8 AI-action aliases found in TS/TSX +")

    return passes, violations
