# tests/unit/api/analytics/test_cost_budget_block.py
"""Budget overlay on the costs report (spec A-6, ADR-094 D6/D8).

Companion to ``test_cost_query_service.py`` (month/trend wiring); shares
its fake fleet via ``_cost_service_helpers``. Pinned here: the
``CostMonthReport.budget`` block is present with exact float fields when a
budget is set, absent (``None``) when unset or when no settings reader is
injected, scoped to the caller's settings row, and judged ``over_budget``
by the SAME ``>=`` boundary as the block-mode gate — one rule, both
surfaces.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from tests.unit.api.analytics._cost_service_helpers import (
    _FakeUsageRepository,
    _make_service,
    _march_rows,
)

from narrare.analytics.service import CostQueryService

if TYPE_CHECKING:
    from narrare.analytics.repository import UsageAggRow, UsageRecordRepository
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository


@dataclass
class _FakeBudgetSettings:
    """Duck-typed ``UserAiSettings`` stand-in (budget columns only)."""

    monthly_budget_usd: Decimal | None
    budget_mode: str = "warn"


class _FakeBudgetSettingsRepo:
    """Fake settings-repo lookup: canned row + call recording."""

    def __init__(self, row: _FakeBudgetSettings) -> None:
        self._row = row
        self.calls: list[uuid.UUID] = []

    async def get(self, user_id: uuid.UUID) -> _FakeBudgetSettings:
        self.calls.append(user_id)
        return self._row


def _make_service_with_budget(
    rows: list[UsageAggRow], settings: _FakeBudgetSettings
) -> tuple[CostQueryService, _FakeBudgetSettingsRepo]:
    """Service over fake usage rows + a fake budget settings repo."""
    fake = _FakeUsageRepository(rows)
    budget_repo = _FakeBudgetSettingsRepo(settings)
    service = CostQueryService(
        cast("UsageRecordRepository", fake),
        budget_settings_repo=cast("UserAiSettingsRepository", budget_repo),
    )
    return service, budget_repo


class TestMonthReportBudgetBlock:
    async def test_budget_set_and_under_spend_yields_block_not_over(self) -> None:
        """March spend 0.019 < budget 1.00 → block present, over_budget False."""
        service, budget_repo = _make_service_with_budget(
            _march_rows(), _FakeBudgetSettings(Decimal("1.00"), "warn")
        )
        user = uuid4()

        report = await service.month_report(user, "2026-03")

        assert budget_repo.calls == [user]  # settings read scoped to the caller
        assert report.budget is not None
        assert report.budget.monthly_budget_usd == 1.0
        assert report.budget.budget_mode == "warn"
        assert report.budget.month_spend_usd == 0.019
        assert report.budget.over_budget is False

    async def test_budget_set_and_spend_over_yields_over_budget(self) -> None:
        """March spend 0.019 ≥ budget 0.005 → over_budget True (warn visible)."""
        service, _ = _make_service_with_budget(
            _march_rows(), _FakeBudgetSettings(Decimal("0.005"), "warn")
        )

        report = await service.month_report(uuid4(), "2026-03")

        assert report.budget is not None
        assert report.budget.over_budget is True

    async def test_budget_at_spend_boundary_is_over(self) -> None:
        """Same ``>=`` boundary as the block-mode gate — one rule, both surfaces."""
        service, _ = _make_service_with_budget(
            _march_rows(), _FakeBudgetSettings(Decimal("0.019"), "block")
        )

        report = await service.month_report(uuid4(), "2026-03")

        assert report.budget is not None
        assert report.budget.over_budget is True

    async def test_block_mode_passes_through(self) -> None:
        service, _ = _make_service_with_budget(
            _march_rows(), _FakeBudgetSettings(Decimal("1"), "block")
        )

        report = await service.month_report(uuid4(), "2026-03")

        assert report.budget is not None
        assert report.budget.budget_mode == "block"

    async def test_no_budget_set_yields_none_block(self) -> None:
        """NULL budget = unset (ADR-094 D7): the report omits the overlay."""
        service, budget_repo = _make_service_with_budget(
            _march_rows(), _FakeBudgetSettings(None, "warn")
        )

        report = await service.month_report(uuid4(), "2026-03")

        assert report.budget is None
        assert budget_repo.calls  # the settings row WAS consulted

    async def test_without_settings_repo_budget_stays_none(self) -> None:
        """Backward-compatible default: no reader injected ⇒ no overlay."""
        service, _ = _make_service(_march_rows())

        report = await service.month_report(uuid4(), "2026-03")

        assert report.budget is None
