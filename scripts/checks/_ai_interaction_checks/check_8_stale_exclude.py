"""Check 8 — Stale-exclude gate for .ai_interaction_exclude entries.

Validates that governed exclusions remain fresh and linked to durable
AUFG lifecycle entries.  Per ai-ux-compliance-v2 §7:

1. Mandatory fields present (owner, gate, reason, exit, added,
   re_evaluated) — already enforced by ``load_exclude_list``.
2. ``re_evaluated`` refreshed at least quarterly (90 days).
3. ``migration-in-progress`` entries must link to an AUFG ID in exit
   or reason.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._shared import ExcludeRegistry

GATE = "check_8_stale_exclude"

# Quarterly refresh window per §7 rule 3.
STALE_WINDOW_DAYS = 90

# AUFG ID pattern for migration-in-progress validation.
_AUFG_PATTERN = re.compile(r"(?:CR-)?AUFG-\d{2}-\d{2,3}")


def _parse_date(date_str: str) -> date | None:
    """Parse YYYY-MM-DD; return None if invalid."""
    try:
        return date.fromisoformat(date_str.strip())
    except ValueError, AttributeError:
        return None


def _is_stale(re_evaluated: str, today: date, window_days: int) -> bool:
    parsed = _parse_date(re_evaluated)
    if parsed is None:
        return True  # Unparseable date = stale/invalid
    return (today - parsed) > timedelta(days=window_days)


def _is_migration_in_progress(reason: str) -> bool:
    return "migration-in-progress" in reason.lower()


def _has_aufg_link(text: str) -> bool:
    return bool(_AUFG_PATTERN.search(text))


def check_stale_exclude(
    registry: ExcludeRegistry,
    today: date | None = None,
) -> tuple[list[str], list[str]]:
    """Check 8: Exclude entries must be fresh and AUFG-linked when migrating.

    Returns ``(passes, violations)``.  Violations identify entries that
    are stale (``re_evaluated`` older than 90 days) or migration entries
    lacking an AUFG ID in their exit/reason fields.
    """
    passes: list[str] = []
    violations: list[str] = []

    if today is None:
        today = date.today()

    if not registry.entries:
        passes.append("No exclude entries — check not applicable")
        return passes, violations

    stale_count = 0
    migration_missing_aufg = 0

    for entry in registry.entries:
        # Rule 2: re_evaluated freshness
        if _is_stale(entry.re_evaluated, today, STALE_WINDOW_DAYS):
            stale_count += 1
            violations.append(
                f"{entry.path}: re_evaluated={entry.re_evaluated} is stale "
                f"(older than {STALE_WINDOW_DAYS} days as of {today.isoformat()})\n"
                f"  -> Refresh re_evaluated date or remove the exclude"
            )

        # Rule 3: migration-in-progress must have AUFG link
        if _is_migration_in_progress(entry.reason):
            combined = f"{entry.reason} {entry.exit_criteria}"
            if not _has_aufg_link(combined):
                migration_missing_aufg += 1
                violations.append(
                    f"{entry.path}: migration-in-progress exclude lacks AUFG ID "
                    f"in reason/exit\n"
                    f"  -> Add CR-AUFG-XX-YY reference or convert to structural category"
                )

    if stale_count == 0:
        passes.append(
            f"All {len(registry.entries)} exclude entries are within "
            f"{STALE_WINDOW_DAYS}-day freshness window +"
        )

    if migration_missing_aufg == 0:
        migration_entries = sum(1 for e in registry.entries if _is_migration_in_progress(e.reason))
        if migration_entries > 0:
            passes.append(
                f"All {migration_entries} migration-in-progress entries have AUFG links +"
            )

    return passes, violations
