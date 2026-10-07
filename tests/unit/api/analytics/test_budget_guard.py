# tests/unit/api/analytics/test_budget_guard.py
"""Unit tests for the DB-backed budget guard (STATS-002, ADR-094, spec A-2/A-4).

``UserBudgetGuard`` is the API-side ``BudgetGuard`` implementation behind
the Core slot (``narrare_core.llm.budget``): sync ``check`` compares the
sink's running UTC-month total against a per-user cached budget config.

Pinned here (unit matrix over the shared fake fleet from
``_budget_guard_helpers``):
- The decision matrix (ADR-094 D8): no budget ⇒ return; ``warn`` ⇒ return;
  ``block`` AND month spend ≥ budget ⇒ ``BudgetExceededError`` (at-budget
  INCLUDED — same ``>=`` boundary as the costs-endpoint badge).
- The required Decimal→float conversion at the raise boundary (Core error
  attrs are float; pyright enforces).
- Lazy per-user config hydration: uncached first check fails open and
  schedules a background refresh; later checks enforce from the cache.
  Config reads never run on the check path itself (ADR-094 D8).
- Write-through invalidation through the REAL A4 hook slot
  (``budget_invalidation``): drop + re-fetch.
- Fail-open degradation: an unreadable config logs a warning instead of
  raising; a guard outside an event loop (sync-only context) no-ops.

The real-app gate flow, startup arming, and the 429 handler registration
live in the companion ``test_budget_gate_app.py``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest
from structlog.testing import capture_logs
from tests.unit.api.analytics._budget_guard_helpers import (
    _FailingSettingsRepo,
    _FakeSettingsRepo,
    _FakeSettingsRow,
    _FakeTotals,
    _make_guard,
    _NullSessionFactory,
    _patch_settings_repo,
    _settle,
)

from narrare.analytics.budget_guard import UserBudgetGuard
from narrare.analytics.budget_invalidation import (
    invalidate_budget_config,
    set_budget_config_invalidator,
)
from narrare_core.llm.budget import set_budget_guard
from narrare_core.shared.errors import BudgetExceededError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from narrare.analytics.contracts import MonthTotalsSource


@pytest.fixture
def user_id() -> UUID:
    return uuid4()


@pytest.fixture
def cleared_slots() -> Iterator[None]:
    """Guarantee both global slots are unset around every test using them."""
    set_budget_guard(None)
    set_budget_config_invalidator(None)
    yield
    set_budget_guard(None)
    set_budget_config_invalidator(None)


# ---------------------------------------------------------------------------
# Decision matrix (ADR-094 D8)
# ---------------------------------------------------------------------------


class TestGuardMatrix:
    async def test_no_budget_never_raises_even_over_spend(
        self, monkeypatch: pytest.MonkeyPatch, user_id: UUID
    ) -> None:
        totals = _FakeTotals()
        totals.set(user_id, Decimal("99"))
        guard, _ = await _make_guard(
            monkeypatch, {user_id: _FakeSettingsRow(monthly_budget_usd=None, budget_mode="block")}
        )

        guard.check(user_id)  # no raise

    async def test_warn_mode_never_raises_even_over_spend(
        self, monkeypatch: pytest.MonkeyPatch, user_id: UUID
    ) -> None:
        totals = _FakeTotals()
        totals.set(user_id, Decimal("99"))
        guard, _ = await _make_guard(
            monkeypatch,
            {user_id: _FakeSettingsRow(monthly_budget_usd=Decimal("10"), budget_mode="warn")},
            totals=totals,
        )

        guard.check(user_id)  # no raise

    async def test_block_mode_under_budget_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch, user_id: UUID
    ) -> None:
        totals = _FakeTotals()
        totals.set(user_id, Decimal("9.99"))
        guard, _ = await _make_guard(
            monkeypatch,
            {user_id: _FakeSettingsRow(monthly_budget_usd=Decimal("10"), budget_mode="block")},
            totals=totals,
        )

        guard.check(user_id)  # no raise

    async def test_block_mode_at_budget_raises(
        self, monkeypatch: pytest.MonkeyPatch, user_id: UUID
    ) -> None:
        """Boundary is ``>=``: at-budget blocks (spend already consumed it)."""
        totals = _FakeTotals()
        totals.set(user_id, Decimal("10"))
        guard, _ = await _make_guard(
            monkeypatch,
            {user_id: _FakeSettingsRow(monthly_budget_usd=Decimal("10"), budget_mode="block")},
            totals=totals,
        )

        with pytest.raises(BudgetExceededError):
            guard.check(user_id)

    async def test_decimal_scale_difference_still_blocks_at_boundary(
        self, monkeypatch: pytest.MonkeyPatch, user_id: UUID
    ) -> None:
        """NUMERIC(12,6) spend vs NUMERIC(10,2) budget compare by VALUE."""
        totals = _FakeTotals()
        totals.set(user_id, Decimal("10.000000"))
        guard, _ = await _make_guard(
            monkeypatch,
            {user_id: _FakeSettingsRow(monthly_budget_usd=Decimal("10.00"), budget_mode="block")},
            totals=totals,
        )

        with pytest.raises(BudgetExceededError):
            guard.check(user_id)

    async def test_block_mode_over_budget_raises_with_float_attrs(
        self, monkeypatch: pytest.MonkeyPatch, user_id: UUID
    ) -> None:
        """Required Decimal→float conversion (Core error attrs are float)."""
        totals = _FakeTotals()
        totals.set(user_id, Decimal("12.5"))
        guard, _ = await _make_guard(
            monkeypatch,
            {user_id: _FakeSettingsRow(monthly_budget_usd=Decimal("10.25"), budget_mode="block")},
            totals=totals,
        )

        with pytest.raises(BudgetExceededError) as exc_info:
            guard.check(user_id)

        error = exc_info.value
        assert error.user_id == user_id
        assert error.code == "BUDGET_EXCEEDED"
        assert isinstance(error.month_spend_usd, float)
        assert isinstance(error.monthly_budget_usd, float)
        assert error.month_spend_usd == 12.5
        assert error.monthly_budget_usd == 10.25

    async def test_zero_budget_in_block_mode_is_a_full_stop(
        self, monkeypatch: pytest.MonkeyPatch, user_id: UUID
    ) -> None:
        """``0`` is a valid budget (ADR-094 D7): any priced spend blocks."""
        totals = _FakeTotals()
        totals.set(user_id, Decimal("0.000001"))
        guard, _ = await _make_guard(
            monkeypatch,
            {user_id: _FakeSettingsRow(monthly_budget_usd=Decimal("0"), budget_mode="block")},
            totals=totals,
        )

        with pytest.raises(BudgetExceededError):
            guard.check(user_id)


# ---------------------------------------------------------------------------
# Lazy config hydration + invalidation (spec A-4/A-7)
# ---------------------------------------------------------------------------


class TestConfigCache:
    async def test_uncached_first_check_fails_open_then_enforces(
        self, monkeypatch: pytest.MonkeyPatch, user_id: UUID
    ) -> None:
        """First check schedules the refresh and passes; the next blocks."""
        totals = _FakeTotals()
        totals.set(user_id, Decimal("12"))
        guard, _ = await _make_guard(
            monkeypatch,
            {user_id: _FakeSettingsRow(monthly_budget_usd=Decimal("10"), budget_mode="block")},
            totals=totals,
            prehydrate_config=False,
        )

        guard.check(user_id)  # uncached ⇒ fail open, refresh scheduled
        await _settle()

        with pytest.raises(BudgetExceededError):
            guard.check(user_id)

    async def test_repeated_uncached_checks_schedule_one_refresh(
        self, monkeypatch: pytest.MonkeyPatch, user_id: UUID
    ) -> None:
        """In-flight dedup: checks before the refresh lands fetch ONCE."""
        repo = _FakeSettingsRepo({user_id: _FakeSettingsRow(monthly_budget_usd=None)})
        guard, _ = await _make_guard(
            monkeypatch,
            {user_id: _FakeSettingsRow(monthly_budget_usd=None)},
            repo=repo,
            prehydrate_config=False,
        )

        guard.check(user_id)
        guard.check(user_id)  # still uncached (task not yet run) — deduped
        guard.check(user_id)
        await _settle()

        assert repo.calls == [user_id]

    async def test_no_budget_config_is_negatively_cached(
        self, monkeypatch: pytest.MonkeyPatch, user_id: UUID
    ) -> None:
        """A cached (None, mode) entry prevents per-check re-fetches."""
        guard, repo = await _make_guard(
            monkeypatch, {user_id: _FakeSettingsRow(monthly_budget_usd=None)}
        )
        assert isinstance(repo, _FakeSettingsRepo)

        guard.check(user_id)
        guard.check(user_id)
        await _settle()
        guard.check(user_id)

        assert repo.calls == [user_id]  # exactly one config read

    async def test_refresh_config_reads_through_settings_repository(
        self, monkeypatch: pytest.MonkeyPatch, user_id: UUID
    ) -> None:
        guard, repo = await _make_guard(
            monkeypatch,
            {user_id: _FakeSettingsRow(monthly_budget_usd=Decimal("5"), budget_mode="warn")},
            prehydrate_config=False,
        )

        await guard.refresh_config(user_id)

        assert isinstance(repo, _FakeSettingsRepo)
        assert repo.calls == [user_id]

    async def test_refresh_config_failure_logs_and_stays_fail_open(
        self, monkeypatch: pytest.MonkeyPatch, user_id: UUID
    ) -> None:
        """Degradation (RULE-11): logged warning, no raise, cache stays empty."""
        totals = _FakeTotals()
        totals.set(user_id, Decimal("99"))
        guard, _ = await _make_guard(
            monkeypatch,
            {user_id: _FakeSettingsRow(monthly_budget_usd=Decimal("1"), budget_mode="block")},
            totals=totals,
            repo=_FailingSettingsRepo(),
        )

        with capture_logs() as logs:
            await guard.refresh_config(user_id)  # must not raise
            await _settle()  # drain any scheduled refresh logging too

        assert any(entry["event"] == "budget_config_refresh_failed" for entry in logs)
        guard.check(user_id)  # still uncached ⇒ fail open

    async def test_invalidation_hook_drops_then_next_check_rehydrates(
        self,
        monkeypatch: pytest.MonkeyPatch,
        user_id: UUID,
        cleared_slots: None,
    ) -> None:
        """Write-through via the REAL A4 slot: drop → next check re-fetches.

        The hook is a pure drop (the settings transaction has NOT
        committed when it fires — an immediate re-fetch would re-cache
        the stale pre-commit row). The next check fails open once and then
        enforces the NEW committed config.
        """
        totals = _FakeTotals()
        totals.set(user_id, Decimal("12"))
        rows = {user_id: _FakeSettingsRow(monthly_budget_usd=Decimal("10"), budget_mode="block")}
        repo = _FakeSettingsRepo(rows)
        guard, _ = await _make_guard(monkeypatch, rows, totals=totals, repo=repo)

        with pytest.raises(BudgetExceededError):
            guard.check(user_id)

        set_budget_config_invalidator(guard.drop_cached_config)
        # The settings write lands (commits): budget raised to 20.
        rows[user_id] = _FakeSettingsRow(monthly_budget_usd=Decimal("20"), budget_mode="block")
        invalidate_budget_config(user_id)

        # Next check post-commit: uncached ⇒ fail open once, refresh scheduled.
        guard.check(user_id)
        await _settle()

        guard.check(user_id)  # no raise against the raised budget

    async def test_drop_cached_config_fails_open_until_refetched(
        self, monkeypatch: pytest.MonkeyPatch, user_id: UUID
    ) -> None:
        """Between drop and the next check's re-fetch nothing enforces (bounded gap)."""
        totals = _FakeTotals()
        totals.set(user_id, Decimal("12"))
        guard, _ = await _make_guard(
            monkeypatch,
            {user_id: _FakeSettingsRow(monthly_budget_usd=Decimal("10"), budget_mode="block")},
            totals=totals,
        )

        guard.drop_cached_config(user_id)

        guard.check(user_id)  # uncached ⇒ no raise this call

    def test_check_outside_event_loop_is_a_noop(
        self, monkeypatch: pytest.MonkeyPatch, user_id: UUID
    ) -> None:
        """Sync-only context (no running loop): nothing scheduled, no crash."""
        _patch_settings_repo(monkeypatch, _FakeSettingsRepo({}))
        guard = UserBudgetGuard(
            totals=cast("MonthTotalsSource", _FakeTotals()),
            session_factory=cast("async_sessionmaker[AsyncSession]", _NullSessionFactory()),
        )

        with capture_logs() as logs:
            guard.check(user_id)

        assert any(entry["event"] == "budget_config_refresh_skipped_no_loop" for entry in logs)
