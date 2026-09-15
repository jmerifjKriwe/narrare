"""Lazy budgets resolution semantics for SeriesHistoryPreviewService (ADR-086 L27).

The factory (``series/dependencies_context_preview.py::
get_series_history_preview_service``) wires a ``LazyModelResolution`` plus a
deferred budgets composition (the M-budget / S4b shape — BOTH the
WRITE-intent routing cascade and the token-limits cascade move past
validation, ``dependencies_beta_reader.py`` precedent); this file pins the
SERVICE-side lazy contract:

- no resolution at construction,
- exactly one composition at first use, idempotent afterwards
  (``ensure_resolved``),
- ``ConfigurationError`` propagates un-swallowed from the entry point
  (RULE-11 — AI-mandatory endpoint), with the ownership gate running
  FIRST (gates stay ahead of resolution),
- the composed budgets flow into the response verbatim — the eager
  factory applied no transformation between cascades and
  ``resolve_context_budgets``, so none appear (WHAT unchanged, only WHEN).

Mirrors ``tests/unit/api/series/test_series_voice_service_lazy_resolution.py``
(ADR-086 L28 precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

import pytest

from narrare.series.series_history_preview_service import SeriesHistoryPreviewService
from narrare.series.series_history_provider import SeriesHistoryProvider
from narrare_core.context.contracts import EffectiveContextBudgets
from narrare_core.series.schemas import Series
from narrare_core.shared.errors import ConfigurationError, ForbiddenError
from tests.fakes.fake_band_summary_repo import FakeBandSummaryRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class _CountingBudgetsFactory:
    """Fake deferred budgets composition — counts invocations, never caches.

    Exposes the service-level lazy seam (ADR-086): the composition (both
    the WRITE-intent routing cascade and the token-limits cascade inside
    the DI factory's closure) must run exactly once, at first use —
    never at construction.
    """

    def __init__(self, budgets: EffectiveContextBudgets) -> None:
        self._budgets = budgets
        self.calls = 0

    async def __call__(self) -> EffectiveContextBudgets:
        self.calls += 1
        return self._budgets


class _RaisingBudgetsFactory:
    """Fake deferred composition — the routing cascade finds no provider."""

    async def __call__(self) -> EffectiveContextBudgets:
        raise ConfigurationError(
            "No AI provider configured.",
            code="NO_AI_PROVIDER",
        )


def _budgets(series_history: int = 16_000) -> EffectiveContextBudgets:
    """Frozen budgets, as the composed ADR-082 chain would return them."""
    return EffectiveContextBudgets(
        context_total=32_000,
        series_history=series_history,
        writing_tier_base=32_000 - series_history,
        reserve_tokens=8_096,
        context_window=128_000,
        source="cascade:uncapped",
    )


def _make_service(
    budgets_factory: Callable[[], Awaitable[EffectiveContextBudgets]],
    *,
    seed: bool = True,
) -> tuple[SeriesHistoryPreviewService, FakeSeriesRepository, UUID, UUID]:
    """Build a SeriesHistoryPreviewService with the lazy seam injected.

    When ``seed`` is True, an owned series is seeded so ``get_preview``
    flows past the ownership gate. Returns
    ``(service, series_repo, series_id, user_id)``.
    """
    series_repo = FakeSeriesRepository()
    user_id = uuid4()
    if seed:
        series = Series(id=uuid4(), user_id=user_id, title="L27 Preview")
        series_repo.seed(series)
        series_id = series.id
    else:
        series_id = uuid4()

    provider = SeriesHistoryProvider(
        novel_repo=cast("Any", None),  # unused by collect_series_band_data
        series_repo=series_repo,
        band_summary_repo=FakeBandSummaryRepository(),
    )
    service = SeriesHistoryPreviewService(
        series_repo=cast("Any", series_repo),
        provider=provider,
        budgets_factory=budgets_factory,
    )
    return service, series_repo, series_id, user_id


class TestLazyResolutionContract:
    """ADR-086 lazy resolution at the SeriesHistoryPreviewService boundary."""

    async def test_no_resolution_at_construction(self) -> None:
        """Construction must not touch either cascade."""
        counting = _CountingBudgetsFactory(_budgets())

        _make_service(counting)

        assert counting.calls == 0

    async def test_ensure_resolved_resolves_once_and_is_idempotent(self) -> None:
        """First use composes the budgets exactly once; repeat calls hit
        the cache."""
        counting = _CountingBudgetsFactory(_budgets())
        service = _make_service(counting)[0]

        first = await service.ensure_resolved()
        second = await service.ensure_resolved()

        assert counting.calls == 1
        assert first is second

    async def test_get_preview_resolves_exactly_once(self) -> None:
        """The entry point is the first-use seam — one composition per
        preview."""
        counting = _CountingBudgetsFactory(_budgets())
        service, _sr, series_id, user_id = _make_service(counting)

        await service.get_preview(series_id, user_id)

        assert counting.calls == 1

    async def test_resolver_configuration_error_propagates_un_swallowed(self) -> None:
        """RULE-11 / ADR-086: the cascades' ``ConfigurationError``
        (unconfigured provider) propagates from the entry point — the
        service never swallows it (AI-mandatory endpoint). The ownership
        gate runs FIRST and passes (seeded repo), so the error comes
        from resolution, proving the gate stays ahead of resolution."""
        service, _sr, series_id, user_id = _make_service(_RaisingBudgetsFactory())

        with pytest.raises(ConfigurationError):
            await service.get_preview(series_id, user_id)

    async def test_ownership_gate_stays_ahead_of_resolution(self) -> None:
        """A non-owned series is rejected with ``ForbiddenError`` and the
        deferred composition is NEVER invoked — the gate precedes
        resolution (eager-world precedence preserved; MUST-NOT-change
        list)."""
        counting = _CountingBudgetsFactory(_budgets())
        service, _sr, _series_id, _user_id = _make_service(counting)

        with pytest.raises(ForbiddenError):
            await service.get_preview(uuid4(), uuid4())

        assert counting.calls == 0

    async def test_composed_budgets_flow_into_response_unchanged(self) -> None:
        """Timing-only invariant: the eager factory computed
        ``resolve_context_budgets`` over the resolved config + limits and
        handed the frozen budgets to the service — the lazy service
        surfaces the SAME values verbatim in the response metadata."""
        budgets = _budgets(series_history=3_000)
        counting = _CountingBudgetsFactory(budgets)
        service, _sr, series_id, user_id = _make_service(counting)

        result = await service.get_preview(series_id, user_id)

        assert result.effective_series_history_budget == 3_000
        assert result.effective_context_total == 32_000
        assert result.effective_tier_base == 29_000
        assert result.model_context_window == 128_000
        assert result.budget_source == "cascade:uncapped"
        assert all(p.token_budget == 3_000 for p in result.previews)
