"""Tests for SeriesHistoryPreviewService (C1 — honesty preview read model).

Domain fakes (ADR-030): FakeSeriesRepository for ownership + settings;
the REAL SeriesHistoryProvider over FakeSeriesRepository /
FakeBandSummaryRepository (its collect_series_band_data landed in this
same task); the REAL Core tier; a canned budgets_provider returning a
frozen EffectiveContextBudgets (the factory's ADR-082 resolution is
pinned by wiring tests, not duplicated here).
"""

from __future__ import annotations

import uuid

import pytest

from narrare.series.band_summary_models import BandSummary
from narrare.series.series_history_preview_contracts import (
    SeriesHistoryPreviewServiceProtocol,
)
from narrare.series.series_history_preview_service import SeriesHistoryPreviewService
from narrare.series.series_history_provider import SeriesHistoryProvider
from narrare_core.context.contracts import EffectiveContextBudgets
from narrare_core.series.schemas import Series
from narrare_core.shared.errors import ForbiddenError
from tests.fakes.fake_band_summary_repo import FakeBandSummaryRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository


def _series(user_id: uuid.UUID) -> Series:
    return Series(id=uuid.uuid4(), user_id=user_id, title="Chronicles")


def _budgets(series_history: int = 16_000) -> EffectiveContextBudgets:
    return EffectiveContextBudgets(
        context_total=32_000,
        series_history=series_history,
        writing_tier_base=32_000 - series_history,
        reserve_tokens=8_096,
        context_window=128_000,
        source="cascade:uncapped",
    )


def _summary(novel_id: uuid.UUID, full: str, short: str) -> BandSummary:
    return BandSummary(novel_id=novel_id, full_summary=full, short_summary=short)


def _make_service(
    *,
    series_repo: FakeSeriesRepository,
    band_repo: FakeBandSummaryRepository | None = None,
    series_history: int = 16_000,
) -> SeriesHistoryPreviewService:
    provider = SeriesHistoryProvider(
        novel_repo=None,  # type: ignore[arg-type] — unused by collect_series_band_data
        series_repo=series_repo,
        band_summary_repo=band_repo or FakeBandSummaryRepository(),
    )
    return SeriesHistoryPreviewService(
        series_repo=series_repo,
        provider=provider,
        budgets_provider=lambda: _budgets(series_history),
    )


class TestOwnership:
    async def test_unknown_series_raises_forbidden(self) -> None:
        service = _make_service(series_repo=FakeSeriesRepository())

        with pytest.raises(ForbiddenError):
            await service.get_preview(uuid.uuid4(), uuid.uuid4())

    async def test_foreign_series_raises_forbidden(self) -> None:
        owner, stranger = uuid.uuid4(), uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(owner))
        series_id = next(iter(series_repo._series))
        service = _make_service(series_repo=series_repo)

        with pytest.raises(ForbiddenError):
            await service.get_preview(series_id, stranger)


class TestWindowRange:
    async def test_default_settings_row_missing_yields_range_1_to_10(self) -> None:
        owner = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series = _series(owner)
        series_repo.seed(series)
        series_repo._settings.pop(series.id)  # fake has no public unset — private pop
        service = _make_service(series_repo=series_repo)

        result = await service.get_preview(series.id, owner)

        assert result.current_window_size == 3
        assert [p.window_size for p in result.previews] == list(range(1, 11))

    async def test_saved_window_within_slider_range(self) -> None:
        owner = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(owner))
        await series_repo.update_settings(
            next(iter(series_repo._series)), {"context_window_size": 7}
        )
        service = _make_service(series_repo=series_repo)

        result = await service.get_preview(next(iter(series_repo._series)), owner)

        assert result.current_window_size == 7
        assert [p.window_size for p in result.previews] == list(range(1, 11))

    async def test_saved_window_above_slider_extends_range(self) -> None:
        """API/MCP can save up to 50 — the preview stays honest for it."""
        owner = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(owner))
        series_id = next(iter(series_repo._series))
        await series_repo.update_settings(series_id, {"context_window_size": 12})
        service = _make_service(series_repo=series_repo)

        result = await service.get_preview(series_id, owner)

        assert result.current_window_size == 12
        assert [p.window_size for p in result.previews] == list(range(1, 13))


class TestComputation:
    async def test_actual_summaries_flow_into_counts(self) -> None:
        owner = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series = _series(owner)
        band_repo = FakeBandSummaryRepository()

        # Three positioned member novels (next-band semantics: all prior).
        # Plain attribute shapes are enough — FakeSeriesRepository.list_novels
        # runs NovelRow.model_validate(n), and NovelRow is
        # extra="allow", from_attributes=True.
        novels = []
        summaries = []
        for position in (1, 2, 3):
            novel_id = uuid.uuid4()
            novels.append(
                type(
                    "NovelRow",
                    (),
                    {
                        "id": novel_id,
                        # user_id is REQUIRED on NovelRow (no default) — the
                        # plain shape must carry it to pass model_validate.
                        "user_id": uuid.uuid4(),
                        "title": f"Band {position}",
                        "series_position": position,
                    },
                )()
            )
            summaries.append(
                _summary(novel_id, full="Full text. " * 80, short=f"Short {position}.")
            )
        series_repo.seed(series, novels=novels)
        band_repo.seed(*summaries)
        service = _make_service(series_repo=series_repo, band_repo=band_repo)

        result = await service.get_preview(series.id, owner)

        entry = next(p for p in result.previews if p.window_size == 10)
        assert entry.bands_total == 3
        assert entry.bands_full == 3
        assert entry.bands_missing == 0
        assert entry.estimated_tokens > 0

    async def test_every_entry_uses_effective_series_history_budget(self) -> None:
        owner = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(owner))
        service = _make_service(series_repo=series_repo, series_history=3_000)

        result = await service.get_preview(next(iter(series_repo._series)), owner)

        assert result.effective_series_history_budget == 3_000
        assert all(p.token_budget == 3_000 for p in result.previews)

    async def test_budget_metadata_passthrough_verbatim(self) -> None:
        owner = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(owner))
        service = _make_service(series_repo=series_repo)

        result = await service.get_preview(next(iter(series_repo._series)), owner)

        assert result.effective_context_total == 32_000
        assert result.effective_tier_base == 16_000
        assert result.model_context_window == 128_000
        assert result.budget_source == "cascade:uncapped"

    async def test_empty_series_yields_zero_counts(self) -> None:
        owner = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(owner))
        service = _make_service(series_repo=series_repo)

        result = await service.get_preview(next(iter(series_repo._series)), owner)

        assert all(p.bands_total == 0 and p.estimated_tokens == 0 for p in result.previews)

    def test_service_satisfies_protocol(self) -> None:
        service = _make_service(series_repo=FakeSeriesRepository())
        assert isinstance(service, SeriesHistoryPreviewServiceProtocol)
