"""Check 9 — Lifecycle sync gate for CR-AUFG IDs.

Ensures every CR-AUFG ID cited in the CR-07 UX audit evidence file
exists in the durable AUFG registry or is explicitly marked
``covered_by_existing_aufg``.  Prevents audit-only CR-AUFG loss per
ai-ux-compliance-v2 §8.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._aufg_helpers import extract_aufg_ids, get_registry_ids, parse_aufg_registry
from ._shared import REPO_ROOT

if TYPE_CHECKING:
    from pathlib import Path

GATE = "check_9_lifecycle_sync"

# Evidence input file (not lifecycle SSOT per §8).
_CR07_AUDIT_PATH = REPO_ROOT / "_audit" / "results" / "content-review" / "cr-07-ux.md"

# Registry lifecycle SSOT.
_REGISTRY_PATH = REPO_ROOT / "docs" / "architecture" / "governance" / "aufg-registry.md"


def check_lifecycle_sync(
    audit_path: Path | None = None,
    registry_path: Path | None = None,
) -> tuple[list[str], list[str]]:
    """Check 9: CR-AUFG IDs in audit must exist in registry.

    Returns ``(passes, violations)``.  Violations list audit-cited
    CR-AUFG IDs that are missing from the durable registry.
    """
    passes: list[str] = []
    violations: list[str] = []

    audit = audit_path or _CR07_AUDIT_PATH
    registry = registry_path or _REGISTRY_PATH

    if not audit.exists():
        passes.append(f"Audit file not found at {audit} — check not applicable")
        return passes, violations

    if not registry.exists():
        violations.append(f"Registry file not found at {registry}")
        return passes, violations

    audit_text = audit.read_text(encoding="utf-8")
    registry_entries = parse_aufg_registry(registry)
    registry_ids = get_registry_ids(registry_entries)

    # Also check for covered_by_existing_aufg markers in the registry text.
    registry_text = registry.read_text(encoding="utf-8")
    covered_markers: set[str] = re_findall_covered(registry_text)

    audit_ids = extract_aufg_ids(audit_text)

    # Filter to CR-AUFG-07-* IDs in the active range (07-07+).
    # CR-AUFG-07-01 through 07-06 are explicitly marked obsolete in the audit:
    # "Vorherige CR-AUFG-07-01 bis 07-06 sind OBSOLETE - ADR-043 hat die dort
    # genannten Probleme gelöst."
    cr07_ids = {
        aid
        for aid in audit_ids
        if aid.startswith("CR-AUFG-07-") and int(aid.rsplit("-", 1)[1]) >= 7
    }

    if not cr07_ids:
        passes.append("No CR-AUFG-07-* IDs found in audit — check not applicable")
        return passes, violations

    missing = cr07_ids - registry_ids - covered_markers

    if missing:
        for aid in sorted(missing):
            violations.append(
                f"{aid} cited in audit ({audit.name}) but missing from registry\n"
                f"  -> Add to {registry.name} or mark covered_by_existing_aufg"
            )
    else:
        passes.append(f"All {len(cr07_ids)} CR-AUFG-07-* IDs from audit are in registry +")

    return passes, violations


def re_findall_covered(text: str) -> set[str]:
    """Find AUFG IDs mentioned near ``covered_by_existing_aufg`` markers.

    This is a heuristic: looks for AUFG IDs in lines containing the
    ``covered_by_existing_aufg`` keyword.
    """
    import re

    results: set[str] = set()
    for line in text.splitlines():
        if "covered_by_existing_aufg" in line.lower():
            ids = re.findall(r"((?:CR-)?AUFG-\d{2}-\d{2,3})", line)
            results.update(ids)
    return results
