"""Tests for Check 8 — Stale-exclude gate."""

from __future__ import annotations

from datetime import date, timedelta

from _ai_interaction_checks._shared import ExcludeEntry, ExcludeRegistry
from _ai_interaction_checks.check_8_stale_exclude import (
    STALE_WINDOW_DAYS,
    _has_aufg_link,
    _is_migration_in_progress,
    _is_stale,
    check_stale_exclude,
)


def _make_entry(
    path: str = "test.tsx",
    reason: str = "hook-internals: test",
    exit_criteria: str = "test done",
    re_evaluated: str = "2026-06-19",
) -> ExcludeEntry:
    return ExcludeEntry(
        path=path,
        owner="Platform",
        gate="check_8_stale_exclude",
        reason=reason,
        exit_criteria=exit_criteria,
        added="2026-01-01",
        re_evaluated=re_evaluated,
        raw_line="",
        line_number=1,
    )


def test_is_stale_returns_false_for_recent_date() -> None:
    today = date(2026, 6, 19)
    assert not _is_stale("2026-06-01", today, STALE_WINDOW_DAYS)


def test_is_stale_returns_true_for_old_date() -> None:
    today = date(2026, 6, 19)
    old = (today - timedelta(days=STALE_WINDOW_DAYS + 1)).isoformat()
    assert _is_stale(old, today, STALE_WINDOW_DAYS)


def test_is_stale_returns_true_for_invalid_date() -> None:
    assert _is_stale("invalid", date(2026, 6, 19), STALE_WINDOW_DAYS)


def test_is_migration_in_progress_detects_keyword() -> None:
    assert _is_migration_in_progress("migration-in-progress: not yet done")
    assert not _is_migration_in_progress("hook-internals: structural")
    assert not _is_migration_in_progress("non-react-extension: TipTap")


def test_has_aufg_link_detects_pattern() -> None:
    assert _has_aufg_link("tracked in CR-AUFG-07-09")
    assert _has_aufg_link("see AUFG-05-12")
    assert not _has_aufg_link("no aufg reference here")


def test_check_stale_exclude_passes_for_fresh_structural_entries() -> None:
    """Structural excludes with fresh dates pass cleanly."""
    registry = ExcludeRegistry()
    registry.entries = [
        _make_entry(reason="hook-internals: structural"),
        _make_entry(reason="non-react-extension: TipTap"),
    ]

    passes, violations = check_stale_exclude(registry, today=date(2026, 6, 19))

    assert violations == []
    assert any("freshness" in p for p in passes)


def test_check_stale_exclude_flags_stale_entry() -> None:
    """Entries with re_evaluated older than 90 days are flagged."""
    registry = ExcludeRegistry()
    registry.entries = [
        _make_entry(re_evaluated="2026-01-01"),  # ~170 days old
    ]

    _, violations = check_stale_exclude(registry, today=date(2026, 6, 19))

    assert len(violations) == 1
    assert "stale" in violations[0]


def test_check_stale_exclude_flags_migration_without_aufg() -> None:
    """migration-in-progress entries without AUFG ID are flagged."""
    registry = ExcludeRegistry()
    registry.entries = [
        _make_entry(
            reason="migration-in-progress: not yet migrated",
            exit_criteria="migration complete",
        ),
    ]

    _, violations = check_stale_exclude(registry, today=date(2026, 6, 19))

    assert any("lacks AUFG ID" in v for v in violations)


def test_check_stale_exclude_passes_migration_with_aufg() -> None:
    """migration-in-progress entries with AUFG ID in exit pass."""
    registry = ExcludeRegistry()
    registry.entries = [
        _make_entry(
            reason="migration-in-progress: tracked in CR-AUFG-07-09",
            exit_criteria="migration complete (CR-AUFG-07-09)",
        ),
    ]

    _, violations = check_stale_exclude(registry, today=date(2026, 6, 19))

    assert not any("lacks AUFG" in v for v in violations)


def test_check_stale_exclude_empty_registry_passes() -> None:
    """Empty registry produces a pass, no violations."""
    registry = ExcludeRegistry()
    passes, violations = check_stale_exclude(registry)

    assert violations == []
    assert any("not applicable" in p.lower() for p in passes)
