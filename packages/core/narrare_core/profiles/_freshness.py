"""Freshness checks for profile data.

Pure timestamp-based staleness detection.  No I/O, no external services.
"""

from __future__ import annotations

from datetime import UTC, datetime


def is_stale(updated_at: str | None, max_age_days: int) -> bool:
    """Check if an ISO-8601 timestamp is older than ``max_age_days``.

    Returns ``False`` when ``updated_at`` is ``None`` or unparsable
    (graceful degradation — absence of timestamp does not trigger the
    staleness warning).
    """
    if not updated_at:
        return False
    try:
        if updated_at.endswith("Z"):
            updated_at = updated_at[:-1] + "+00:00"
        parsed = datetime.fromisoformat(updated_at)
        age = (datetime.now(UTC) - parsed).days
        return age > max_age_days
    except ValueError, TypeError:
        return False


def check_freshness_warning(
    name: str,
    updated_at: str | None,
    max_age_days: int,
) -> str | None:
    """Return a freshness warning string if stale, else ``None``."""
    if is_stale(updated_at, max_age_days) and updated_at:
        return f"Voice profile for '{name}' last updated {updated_at} (>{max_age_days} days ago)"
    return None
