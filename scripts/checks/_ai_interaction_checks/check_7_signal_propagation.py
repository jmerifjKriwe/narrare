"""Check 7 — Signal propagation gate for useAIOperation consumers.

Verifies that files using ``useAIOperation`` define ``execute`` callbacks
that accept and propagate a ``signal`` parameter to the transport layer.
UI-only cancel (local state change) without signal propagation is
non-compliant per §16.2.

Motivated by CR-AUFG-07-11 (KB Enhance Cancel Signal Propagation).
"""

from __future__ import annotations

import re
from pathlib import Path

from ._shared import WEB_DIR, ExcludeRegistry, display_path, rg_files

GATE = "check_7_signal_propagation"

# Files that contain ``execute:`` definitions using useAIOperation.
_USE_AI_OP_PATTERN = r"useAIOperation\s*\("

# Match ``execute:`` callback definitions and capture the parameter list.
# Handles: execute: (signal) => ..., execute: async (signal) => ...,
#           execute: () => ..., execute: async () => ...
_EXECUTE_PATTERN = re.compile(
    r"execute\s*:\s*(?:async\s*)?\(\s*([^)]*)\)\s*(?:=>|{)",
    re.MULTILINE,
)

# Test infrastructure paths are excluded from this check.
_TEST_PATH_PATTERNS = [
    re.compile(r"/__tests__/"),
    re.compile(r"\.test\.(ts|tsx)$"),
    re.compile(r"\.spec\.(ts|tsx)$"),
    re.compile(r"ai-test-helpers\.ts$"),
    re.compile(r"setup\.ts$"),
]


def _is_test_file(rel_path: str) -> bool:
    return any(p.search(rel_path) for p in _TEST_PATH_PATTERNS)


def _find_use_ai_operation_files() -> list[Path]:
    """Find TS/TSX files that invoke useAIOperation."""
    files = rg_files(
        _USE_AI_OP_PATTERN,
        "-g",
        "*.ts",
        "-g",
        "*.tsx",
        path=str(WEB_DIR),
    )
    return sorted(Path(f) for f in files)


def _check_execute_signal(content: str) -> list[str]:
    """Return violation messages for execute callbacks missing signal param.

    Examines each ``execute:`` definition in *content* and flags those
    whose parameter list does not contain ``signal`` (case-insensitive).
    """
    issues: list[str] = []
    for match in _EXECUTE_PATTERN.finditer(content):
        params = match.group(1).strip()
        if not params:
            # execute: () => ...  — no parameter at all
            line_num = content[: match.start()].count("\n") + 1
            issues.append(
                f"L{line_num}: execute callback has no signal parameter\n"
                f"    {match.group(0).strip()[:100]}"
            )
        elif "signal" not in params.lower():
            # execute: (foo) => ...  — parameter exists but isn't 'signal'
            line_num = content[: match.start()].count("\n") + 1
            issues.append(
                f"L{line_num}: execute callback parameter '{params}' is not 'signal'\n"
                f"    {match.group(0).strip()[:100]}"
            )
    return issues


def check_signal_propagation(
    registry: ExcludeRegistry,
) -> tuple[list[str], list[str]]:
    """Check 7: useAIOperation execute callbacks must propagate signal.

    Returns ``(passes, violations)``.  Violations identify files where
    ``execute`` is defined without a ``signal`` parameter or with a
    differently-named parameter.
    """
    passes: list[str] = []
    violations: list[str] = []

    files = _find_use_ai_operation_files()
    if not files:
        passes.append("No useAIOperation consumers found — check not applicable")
        return passes, violations

    checked = 0
    for fp in files:
        rel = display_path(fp)

        if _is_test_file(rel):
            continue

        if registry.is_excluded(rel, gate=GATE):
            continue

        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        execute_issues = _check_execute_signal(content)
        checked += 1

        if execute_issues:
            for issue in execute_issues:
                violations.append(
                    f"{rel}: execute callback does not propagate AbortSignal\n"
                    f"  {issue}\n"
                    f"  -> execute must accept (signal) and pass it to the API wrapper\n"
                    f"  -> UI-only cancel without transport signal is non-compliant (§16.2)"
                )
        else:
            passes.append(f"{rel} execute callbacks propagate signal +")

    if checked == 0:
        passes.append("No production useAIOperation consumers with execute callbacks to check")

    return passes, violations
