# tests/unit/api/analytics/_budget_guard_helpers.py
"""Shared fakes + helpers for the budget-guard test modules (ADR-030 fakes).

Split out of ``test_budget_guard.py`` (RULE-04): the guard unit tests and
the real-app gate/arming tests share the same fake fleet — totals source,
settings repository fakes, null session factory, and the real-app gate
probe (auth-bound attribution → Core gate → guard → 429 handler).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, cast
from uuid import UUID

# Module-level on purpose: this file uses PEP 563 annotations, so FastAPI
# resolves the probe route's dependency annotations against MODULE globals
# (function-local imports are invisible to get_type_hints).
from narrare._app.dependencies import CurrentUserIdDep, get_current_user_id
from narrare.analytics import budget_guard as budget_guard_mod
from narrare.analytics.budget_guard import UserBudgetGuard
from narrare.analytics.usage_sink import SqlUsageEventSink
from narrare_core.llm.budget import check_budget, get_budget_guard, set_budget_guard
from narrare_core.llm.usage_events import usage_user_id

if TYPE_CHECKING:
    from datetime import datetime

    import pytest
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from narrare.analytics.contracts import MonthTotalsSource


class _FakeTotals:
    """``MonthTotalsSource`` fake: mutable per-user month totals."""

    def __init__(self) -> None:
        self._totals: dict[UUID, Decimal] = {}

    def set(self, user_id: UUID, value: Decimal) -> None:
        self._totals[user_id] = value

    def month_total(self, user_id: UUID) -> Decimal:
        return self._totals.get(user_id, Decimal("0"))


@dataclass
class _FakeSettingsRow:
    """Duck-typed ``UserAiSettings`` stand-in (budget columns only)."""

    monthly_budget_usd: Decimal | None
    budget_mode: str = "warn"


class _FakeSettingsRepo:
    """Fake ``UserAiSettingsRepository``: canned rows + call recording."""

    def __init__(self, rows: dict[UUID, _FakeSettingsRow]) -> None:
        self._rows = rows
        self.calls: list[UUID] = []

    async def get(self, user_id: UUID) -> _FakeSettingsRow:
        self.calls.append(user_id)
        return self._rows[user_id]


class _FailingSettingsRepo:
    """Fake repository that always fails — degradation path."""

    async def get(self, user_id: UUID) -> _FakeSettingsRow:
        raise RuntimeError("db down")


class _NullSession:
    """Session fake: the fake repos never touch it."""


class _NullSessionCtx:
    async def __aenter__(self) -> _NullSession:
        return _NullSession()

    async def __aexit__(self, *args: object) -> None:
        del args


class _NullSessionFactory:
    """Stands in for ``async_sessionmaker[AsyncSession]`` (never connects)."""

    def __call__(self) -> _NullSessionCtx:
        return _NullSessionCtx()


def _patch_settings_repo(
    monkeypatch: pytest.MonkeyPatch, repo: _FakeSettingsRepo | _FailingSettingsRepo
) -> None:
    """Replace the guard's repository constructor seam (fake, RULE-23 cast)."""

    class _RepoFactory:
        def __init__(self, session: _NullSession) -> None:
            del session

        async def get(self, user_id: UUID) -> _FakeSettingsRow:
            return await repo.get(user_id)

    monkeypatch.setattr(budget_guard_mod, "UserAiSettingsRepository", _RepoFactory)


async def _make_guard(
    monkeypatch: pytest.MonkeyPatch,
    rows: dict[UUID, _FakeSettingsRow] | None = None,
    *,
    totals: _FakeTotals | None = None,
    repo: _FakeSettingsRepo | _FailingSettingsRepo | None = None,
    prehydrate_config: bool = True,
) -> tuple[UserBudgetGuard, _FakeSettingsRepo | _FailingSettingsRepo]:
    """Guard over fakes; config cached through the REAL refresh path."""
    if repo is None:
        assert rows is not None
        repo = _FakeSettingsRepo(rows)
    _patch_settings_repo(monkeypatch, repo)
    guard = UserBudgetGuard(
        totals=cast("MonthTotalsSource", totals or _FakeTotals()),
        session_factory=cast("async_sessionmaker[AsyncSession]", _NullSessionFactory()),
    )
    if prehydrate_config:
        for user_id in rows or {}:
            await guard.refresh_config(user_id)
    return guard, repo


async def _settle() -> None:
    """Let scheduled background refresh tasks run to completion."""
    for _ in range(10):
        await asyncio.sleep(0)


_TEST_USER = "00000000-0000-0000-0000-0000000000be"


async def _binding_auth() -> str:
    """Auth override mirroring the real dependency: binds usage attribution.

    Async like the real ``get_current_user_id`` — a sync override would run
    in the threadpool and its ``usage_user_id`` set would NOT propagate
    back to the request task's context.
    """
    usage_user_id.set(UUID(_TEST_USER))
    return _TEST_USER


def _gate_app() -> object:

    from narrare._app.main import create_app

    app = create_app(test_mode=True)
    app.dependency_overrides[get_current_user_id] = _binding_auth

    @app.get("/_test/budget-gate")
    async def _budget_gate(user_id: CurrentUserIdDep) -> dict[str, bool]:
        del user_id  # the override's SIDE EFFECT (attribution bind) is what matters
        check_budget(usage_user_id.get())
        return {"ok": True}

    return app


async def _gate_status(
    monkeypatch: pytest.MonkeyPatch,
    *,
    budget: Decimal | None,
    mode: str,
    month_spend: Decimal,
) -> tuple[int, dict[str, object]]:
    """Drive the real app's gate probe with an armed real guard."""
    from httpx import ASGITransport, AsyncClient

    user = UUID(_TEST_USER)
    totals = _FakeTotals()
    totals.set(user, month_spend)
    rows = {user: _FakeSettingsRow(monthly_budget_usd=budget, budget_mode=mode)}
    guard, _ = await _make_guard(monkeypatch, rows, totals=totals)
    set_budget_guard(guard)
    try:
        app = cast("FastAPI", _gate_app())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/_test/budget-gate")
            return response.status_code, dict(response.json())
    finally:
        set_budget_guard(None)


def _hydration_repo_class(
    totals: dict[UUID, Decimal] | None,
) -> type[object]:
    """Fake analytics repository class: seeded totals, or a failure when None.

    A CLASS (not instance) — ``arm_budget_guard`` constructs the
    repository with the session positionally, so the seed must ride in a
    closure, exactly like the sink tests' ``_FakeRepository``.
    """

    class _FakeHydrationRepo:
        def __init__(self, session: object) -> None:
            del session

        async def month_spend_by_user(self, start: object) -> dict[UUID, Decimal]:
            del start
            if totals is None:
                raise RuntimeError("db down")
            return totals

    return _FakeHydrationRepo


async def _arm(
    monkeypatch: pytest.MonkeyPatch,
    totals: dict[UUID, Decimal] | None,
    sink_clock: datetime,
) -> tuple[UserBudgetGuard, SqlUsageEventSink]:
    from narrare.analytics import repository as repository_mod

    monkeypatch.setattr(repository_mod, "UsageRecordRepository", _hydration_repo_class(totals))
    sink = SqlUsageEventSink(
        cast("async_sessionmaker[AsyncSession]", _NullSessionFactory()),
        clock=lambda: sink_clock,
    )
    await budget_guard_mod.arm_budget_guard(
        sink, cast("async_sessionmaker[AsyncSession]", _NullSessionFactory())
    )
    guard = get_budget_guard()
    assert isinstance(guard, UserBudgetGuard)
    return guard, sink
