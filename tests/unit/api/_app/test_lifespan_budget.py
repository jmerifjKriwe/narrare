# tests/unit/api/_app/test_lifespan_budget.py
"""Budget-guard lifecycle in ``narrare._app.lifespan`` (STATS-002, ADR-094 D5).

Companion to ``test_lifespan.py`` (DB version, migrations, logging); shares
its fake/patch fleet via ``_lifespan_helpers``. Pinned here: startup arms
the gate AFTER sink registration (hydration totals land in the sink, guard
+ invalidator slots registered, non-test mode only), and shutdown clears
both slots BEFORE the sink — never leaking global seams across lifecycles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import narrare._app.lifespan as lifespan_mod
from tests.unit.api._app._lifespan_helpers import (
    _FakeSettings,
    _make_app,
    _no_budget_settings,
    _noop_async,
    _patch_common,
    _returning_async,
)

if TYPE_CHECKING:
    import pytest


class TestLifespanBudgetGuard:
    async def test_budget_guard_armed_hydrated_and_cleared(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ADR-094 D5 arming: startup hydrates + arms; shutdown clears both slots."""
        from decimal import Decimal
        from uuid import uuid4

        from narrare.analytics import budget_guard as budget_guard_mod
        from narrare.analytics import budget_invalidation
        from narrare.analytics.budget_guard import UserBudgetGuard
        from narrare.analytics.usage_sink import SqlUsageEventSink
        from narrare_core.llm.budget import get_budget_guard
        from narrare_core.llm.usage_events import get_usage_event_sink

        settings = _FakeSettings(is_test=False)
        _patch_common(monkeypatch, settings)
        monkeypatch.setattr(lifespan_mod, "_run_pending_migrations", _noop_async)
        monkeypatch.setattr(lifespan_mod, "_run_stale_cleanup", _returning_async(0))
        monkeypatch.setattr("narrare._app.database.dispose_database", _noop_async)

        # Hydration repository fake: seeded totals + call recording. The
        # session factory stays REAL but never connects (the fake repo
        # never executes — sessions connect lazily on first execute).
        spender = uuid4()
        hydration_calls: list[object] = []

        class _FakeHydrationRepo:
            def __init__(self, session: object) -> None:
                del session
                hydration_calls.append("constructed")

            async def month_spend_by_user(self, start: object) -> dict:
                hydration_calls.append(start)
                return {spender: Decimal("7.5")}

        monkeypatch.setattr(
            "narrare.analytics.repository.UsageRecordRepository", _FakeHydrationRepo
        )
        # Config refresh repository fake: no budget → guard no-ops checks.
        monkeypatch.setattr(
            budget_guard_mod,
            "UserAiSettingsRepository",
            type("_NoBudgetRepo", (), {"get": staticmethod(_no_budget_settings)}),
        )

        app = _make_app()
        async with lifespan_mod.lifespan(app):
            guard = get_budget_guard()
            assert isinstance(guard, UserBudgetGuard)
            assert budget_invalidation._invalidator is not None  # pyright: ignore[reportPrivateUsage]
            sink = get_usage_event_sink()
            assert isinstance(sink, SqlUsageEventSink)  # narrows to the read surface
            assert sink.month_total(spender) == Decimal("7.5")  # hydrated

        assert get_budget_guard() is None  # cleared at shutdown
        assert budget_invalidation._invalidator is None  # pyright: ignore[reportPrivateUsage]
        assert get_usage_event_sink() is None
        assert len(hydration_calls) == 2  # constructed once, queried once

    async def test_budget_guard_not_armed_in_test_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test mode never arms the gate (mirrors migrations/cleanup gating)."""
        from narrare_core.llm.budget import get_budget_guard

        settings = _FakeSettings(is_test=True)
        _patch_common(monkeypatch, settings)

        app = _make_app()
        async with lifespan_mod.lifespan(app):
            assert get_budget_guard() is None
