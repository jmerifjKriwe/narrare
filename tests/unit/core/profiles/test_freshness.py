"""Tests for freshness checks.

Covers:
1. is_stale — None, empty, valid, invalid, Z-suffix, edge cases
2. check_freshness_warning — returns warning or None correctly
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from narrare_core.profiles._freshness import check_freshness_warning, is_stale

# ---------------------------------------------------------------------------
# is_stale
# ---------------------------------------------------------------------------


class TestIsStale:
    """is_stale timestamp freshness detection."""

    def test_returns_false_for_none(self) -> None:
        assert is_stale(None, 30) is False

    def test_returns_false_for_empty_string(self) -> None:
        assert is_stale("", 30) is False

    def test_returns_false_for_recent_timestamp(self) -> None:
        recent = (datetime.now(UTC) - timedelta(days=5)).isoformat()
        assert is_stale(recent, 30) is False

    def test_returns_true_for_old_timestamp(self) -> None:
        old = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        assert is_stale(old, 30) is True

    def test_boundary_exactly_max_age(self) -> None:
        """Exactly max_age_days is NOT stale (> check)."""
        exact = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        assert is_stale(exact, 30) is False

    def test_boundary_one_day_over(self) -> None:
        """One day over max_age_days IS stale."""
        over = (datetime.now(UTC) - timedelta(days=31)).isoformat()
        assert is_stale(over, 30) is True

    def test_handles_z_suffix(self) -> None:
        """ISO-8601 with 'Z' suffix is parsed correctly."""
        old = (datetime.now(UTC) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert is_stale(old, 30) is True

    def test_returns_false_for_invalid_string(self) -> None:
        assert is_stale("not-a-date", 30) is False

    def test_returns_false_for_garbage_data(self) -> None:
        assert is_stale("2025-13-45T99:99:99", 30) is False

    def test_returns_false_for_future_timestamp(self) -> None:
        """Future timestamps should not be considered stale."""
        future = (datetime.now(UTC) + timedelta(days=10)).isoformat()
        assert is_stale(future, 30) is False

    def test_zero_max_age(self) -> None:
        """max_age_days=0 → any non-null, non-future timestamp is stale."""
        recent = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        assert is_stale(recent, 0) is True

    def test_timestamp_just_now(self) -> None:
        """Timestamp from 1 second ago is not stale."""
        just_now = datetime.now(UTC).isoformat()
        assert is_stale(just_now, 0) is False


# ---------------------------------------------------------------------------
# check_freshness_warning
# ---------------------------------------------------------------------------


class TestCheckFreshnessWarning:
    """check_freshness_warning returns warning string or None."""

    def test_returns_none_when_fresh(self) -> None:
        recent = (datetime.now(UTC) - timedelta(days=5)).isoformat()
        assert check_freshness_warning("Alice", recent, 30) is None

    def test_returns_none_when_updated_at_none(self) -> None:
        assert check_freshness_warning("Alice", None, 30) is None

    def test_returns_warning_when_stale(self) -> None:
        old = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        result = check_freshness_warning("Alice", old, 30)
        assert result is not None
        assert "Voice profile for 'Alice'" in result
        assert ">30 days ago" in result

    def test_warning_contains_timestamp(self) -> None:
        old = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        result = check_freshness_warning("Bob", old, 30)
        assert result is not None
        assert old in result

    def test_returns_none_when_updated_at_empty(self) -> None:
        assert check_freshness_warning("Alice", "", 30) is None
