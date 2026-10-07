# tests/unit/api/analytics/test_budget_gate_app.py
"""Budget gate on the REAL app + startup arming (STATS-002, ADR-094).

Companion to ``test_budget_guard.py`` (guard unit matrix); shares its fake
fleet via ``_budget_guard_helpers``. Pinned here:

- End-to-end gate flow on the REAL app: auth-bound attribution → Core gate
  → guard → ``BudgetExceededError`` → the app-registered 429 handler
  (200 under budget; 429 at/above in block mode; warn and no-budget never
  block; an unset guard — post-shutdown state — is a no-op).
- ``arm_budget_guard`` startup arming: totals hydrated into the sink, guard
  + invalidator slots registered; hydration failure degrades fail-open.
- The 429 handler registration beats the generic ``NarrareError`` mapping
  (MRO-specific resolution — the probe fails if the generic 400 wins).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest
from tests.unit.api.analytics._budget_guard_helpers import (
    _TEST_USER,
    _arm,
    _FakeSettingsRow,
    _FakeTotals,
    _gate_app,
    _gate_status,
    _make_guard,
)

from narrare_core.llm.budget import get_budget_guard, set_budget_guard
from narrare_core.shared.errors import BudgetExceededError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi import FastAPI


@pytest.fixture
def cleared_slots() -> Iterator[None]:
    """Guarantee both global slots are unset around every test using them."""
    from narrare.analytics.budget_invalidation import set_budget_config_invalidator

    set_budget_guard(None)
    set_budget_config_invalidator(None)
    yield
    set_budget_guard(None)
    set_budget_config_invalidator(None)


class TestRealAppGateFlow:
    """Auth attribution → Core gate → guard → 429 through the REAL app."""

    async def test_under_budget_block_mode_returns_200(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        status, body = await _gate_status(
            monkeypatch, budget=Decimal("10"), mode="block", month_spend=Decimal("9.99")
        )
        assert status == 200
        assert body == {"ok": True}

    async def test_at_budget_block_mode_returns_429(self, monkeypatch: pytest.MonkeyPatch) -> None:
        status, body = await _gate_status(
            monkeypatch, budget=Decimal("10"), mode="block", month_spend=Decimal("10")
        )
        assert status == 429
        assert body["code"] == "BUDGET_EXCEEDED"
        assert "Monthly budget exceeded" in str(body["detail"])

    async def test_over_budget_block_mode_returns_429(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        status, _ = await _gate_status(
            monkeypatch, budget=Decimal("10"), mode="block", month_spend=Decimal("42")
        )
        assert status == 429

    async def test_over_budget_warn_mode_never_blocks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        status, body = await _gate_status(
            monkeypatch, budget=Decimal("1"), mode="warn", month_spend=Decimal("99")
        )
        assert status == 200
        assert body == {"ok": True}

    async def test_no_budget_never_blocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        status, body = await _gate_status(
            monkeypatch, budget=None, mode="block", month_spend=Decimal("99")
        )
        assert status == 200
        assert body == {"ok": True}

    async def test_unset_guard_after_shutdown_is_a_noop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Post-shutdown state (guard cleared): the gate must never 429."""
        from httpx import ASGITransport, AsyncClient

        user = UUID(_TEST_USER)
        totals = _FakeTotals()
        totals.set(user, Decimal("99"))
        rows = {user: _FakeSettingsRow(monthly_budget_usd=Decimal("1"), budget_mode="block")}
        guard, _ = await _make_guard(monkeypatch, rows, totals=totals)
        set_budget_guard(guard)
        set_budget_guard(None)  # the shutdown step
        try:
            app = cast("FastAPI", _gate_app())
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/_test/budget-gate")
            assert response.status_code == 200
        finally:
            set_budget_guard(None)


class TestArmBudgetGuard:
    async def test_hydrates_sink_and_arms_slots(
        self, monkeypatch: pytest.MonkeyPatch, cleared_slots: None
    ) -> None:
        """Startup arming: totals into the sink, guard + invalidator registered."""
        spender = uuid4()
        guard, sink = await _arm(
            monkeypatch, {spender: Decimal("7.5")}, datetime(2026, 10, 7, tzinfo=UTC)
        )

        assert sink.month_total(spender) == Decimal("7.5")
        # Armed via the Core slot.
        assert get_budget_guard() is guard

    async def test_hydration_failure_fails_open_with_empty_totals(
        self, monkeypatch: pytest.MonkeyPatch, cleared_slots: None
    ) -> None:
        """Unreadable totals ⇒ empty hydration + armed fail-open guard (logged)."""
        guard, sink = await _arm(monkeypatch, None, datetime(2026, 10, 7, tzinfo=UTC))

        assert sink.month_total(uuid4()) == Decimal("0")
        guard.check(uuid4())  # uncached ⇒ no raise despite arming


class TestBudgetExceededHandlerRegistration:
    def test_budget_exceeded_maps_to_429_with_code(self) -> None:
        from fastapi.testclient import TestClient

        from narrare._app.main import create_app

        user = uuid4()
        error = BudgetExceededError(user, month_spend_usd=12.5, monthly_budget_usd=10.0)
        app = create_app(test_mode=True)

        @app.get("/_test/budget-error")
        def _raise_budget_error() -> None:
            raise BudgetExceededError(user, month_spend_usd=12.5, monthly_budget_usd=10.0)

        client = TestClient(app)
        response = client.get("/_test/budget-error")

        assert response.status_code == 429
        assert response.json() == {"detail": str(error), "code": "BUDGET_EXCEEDED"}
