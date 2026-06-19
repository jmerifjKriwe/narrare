"""Check 11 — Resolution evidence gate for AUFG registry entries.

Ensures no registry entry is set to ``resolved`` without implementation
files and enforcement evidence named in its Exit evidence block.  Per
ai-ux-compliance-v2 §6 gate 7 and §8 lifecycle discipline.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ._aufg_helpers import parse_aufg_registry
from ._shared import REPO_ROOT

if TYPE_CHECKING:
    from pathlib import Path

    from ._aufg_helpers import AufgEntry

GATE = "check_11_resolution_evidence"

_REGISTRY_PATH = REPO_ROOT / "docs" / "architecture" / "governance" / "aufg-registry.md"

# Patterns that indicate implementation/governance evidence files.
_IMPL_FILE_PATTERN = re.compile(r"[a-z_./\-]+\.(?:py|ts|tsx|js|jsx|yaml|yml|json|toml|md)")

# Patterns that indicate enforcement evidence.
_ENFORCEMENT_KEYWORDS = [
    "check",
    "checker",
    "gate",
    "test",
    "pytest",
    "ruff",
    "pyright",
    "ci",
    "enforce",
    "block",
]


def _has_implementation_files(entry: AufgEntry) -> bool:
    """Check if the exit evidence references implementation files."""
    if entry.implementation_files:
        return True
    return bool(_IMPL_FILE_PATTERN.search(entry.exit_evidence_text))


def _has_enforcement_evidence(entry: AufgEntry) -> bool:
    """Check if the exit evidence mentions enforcement/checker/test evidence."""
    text_lower = entry.exit_evidence_text.lower()
    return any(kw in text_lower for kw in _ENFORCEMENT_KEYWORDS)


def _has_non_pending_evidence(entry: AufgEntry) -> bool:
    """Check if exit evidence is substantive (not just 'Pending')."""
    text = entry.exit_evidence_text.strip()
    if not text:
        return False
    # Reject pure "Pending" evidence.
    return not text.lower().startswith("pending")


def check_resolution_evidence(
    registry_path: Path | None = None,
) -> tuple[list[str], list[str]]:
    """Check 11: Resolved AUFG entries need implementation + enforcement evidence.

    Returns ``(passes, violations)``.
    """
    passes: list[str] = []
    violations: list[str] = []

    reg_path = registry_path or _REGISTRY_PATH

    if not reg_path.exists():
        violations.append(f"Registry file not found: {reg_path}")
        return passes, violations

    entries = parse_aufg_registry(reg_path)
    resolved_entries = [e for e in entries if e.status == "resolved"]

    if not resolved_entries:
        passes.append("No resolved AUFG entries — check not applicable")
        return passes, violations

    missing_impl = 0
    missing_enforcement = 0
    pending_only = 0

    for entry in resolved_entries:
        if not _has_non_pending_evidence(entry):
            pending_only += 1
            violations.append(
                f"{entry.aufg_id}: status 'resolved' but exit evidence is "
                f"missing or 'Pending'\n"
                f"  -> Add implementation files and enforcement evidence"
            )
            continue

        if not _has_implementation_files(entry):
            missing_impl += 1
            violations.append(
                f"{entry.aufg_id}: status 'resolved' but no implementation "
                f"files in exit evidence\n"
                f"  -> Reference source files in the Exit evidence block"
            )

        if not _has_enforcement_evidence(entry):
            missing_enforcement += 1
            violations.append(
                f"{entry.aufg_id}: status 'resolved' but no enforcement "
                f"evidence (test/checker/gate) in exit evidence\n"
                f"  -> Reference tests, checkers, or CI gates that prevent regression"
            )

    clean_count = len(resolved_entries) - missing_impl - missing_enforcement - pending_only
    if clean_count == len(resolved_entries):
        passes.append(
            f"All {len(resolved_entries)} resolved AUFG entries have "
            f"implementation + enforcement evidence +"
        )

    return passes, violations
