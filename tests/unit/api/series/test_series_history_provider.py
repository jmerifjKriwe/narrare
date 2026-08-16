"""Tests for SeriesHistoryProvider (Spec 2, Task 7 — Backend→Core bridge).

The provider is the RULE-07 boundary: it pre-fetches BandSummary data +
novel positions/titles (Backend repos), builds :class:`BandSummaryData`
(Core), and calls :class:`SeriesHistoryTier.assemble` (Core). The writing
service consumes the resulting string and injects it as
``{{series_history}}``.

These tests use the existing domain fakes (ADR-030 — Fake-based). The Core
tier is the real :class:`SeriesHistoryTier` (pure formatting); only the
repos are faked.
"""

from __future__ import annotations

import uuid

import pytest

from narrare.series.band_summary_models import BandSummary
from narrare.series.series_history_provider import SeriesHistoryProvider
from narrare_core.series.schemas import NovelRow, Series, SeriesSettings
from tests.fakes.fake_band_summary_repo import FakeBandSummaryRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _series(series_id: uuid.UUID | None = None) -> Series:
    return Series(
        id=series_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="The Chronicles",
    )


def _novel(
    *,
    series_id: uuid.UUID,
    position: int,
    title: str = "Untitled",
    novel_id: uuid.UUID | None = None,
):
    """Build a bare novel-shape object FakeNovelRepository can store."""
    from narrare.novels.models import Novel

    n = Novel()
    n.id = novel_id or uuid.uuid4()
    n.user_id = uuid.uuid4()
    n.title = title
    n.author = ""
    n.genre = ""
    n.writing_language = "en"
    n.is_demo = False
    n.series_id = series_id
    n.series_position = position
    return n


def _novel_row(
    *,
    series_id: uuid.UUID,
    position: int | None,
    title: str = "Untitled",
    novel_id: uuid.UUID | None = None,
) -> NovelRow:
    return NovelRow(
        id=novel_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        series_id=series_id,
        series_position=position,
        title=title,
    )


def _band_summary(
    novel_id: uuid.UUID,
    *,
    full: str | None = None,
    short: str | None = None,
    override: str | None = None,
) -> BandSummary:
    return BandSummary(
        novel_id=novel_id,
        full_summary=full,
        short_summary=short,
        override=override,
    )


def _make_provider(
    *,
    novel_repo: FakeNovelRepository | None = None,
    series_repo: FakeSeriesRepository | None = None,
    band_repo: FakeBandSummaryRepository | None = None,
) -> tuple[
    SeriesHistoryProvider, FakeNovelRepository, FakeSeriesRepository, FakeBandSummaryRepository
]:
    novel_repo = novel_repo or FakeNovelRepository()
    series_repo = series_repo or FakeSeriesRepository()
    band_repo = band_repo or FakeBandSummaryRepository()
    provider = SeriesHistoryProvider(
        novel_repo=novel_repo,  # type: ignore[arg-type]
        series_repo=series_repo,  # type: ignore[arg-type]
        band_summary_repo=band_repo,  # type: ignore[arg-type]
    )
    return provider, novel_repo, series_repo, band_repo


# ---------------------------------------------------------------------------
# assemble_series_history — standalone / graceful degradation
# ---------------------------------------------------------------------------


class TestAssembleStandaloneAndEdges:
    """RULE-11: standalone + edge cases return "" without crashing."""

    @pytest.mark.asyncio
    async def test_standalone_novel_returns_empty(self) -> None:
        """A novel with no series_id contributes no series history."""
        from narrare.novels.models import Novel

        novel_repo = FakeNovelRepository()
        standalone = Novel()
        standalone.id = uuid.uuid4()
        standalone.user_id = uuid.uuid4()
        standalone.title = "Standalone"
        standalone.series_id = None
        standalone.series_position = None
        novel_repo.seed(standalone)

        provider, _, _, _ = _make_provider(novel_repo=novel_repo)

        result = await provider.assemble_series_history(standalone.id)

        assert result == ""

    @pytest.mark.asyncio
    async def test_missing_novel_returns_empty(self) -> None:
        provider, _, _, _ = _make_provider()

        result = await provider.assemble_series_history(uuid.uuid4())

        assert result == ""

    @pytest.mark.asyncio
    async def test_band_one_no_prior_returns_empty(self) -> None:
        """The first band has no predecessors → empty."""
        series_id = uuid.uuid4()
        current = _novel(series_id=series_id, position=1, title="Band One")
        novel_repo = FakeNovelRepository()
        novel_repo.seed(current)
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(series_id), novels=[current])

        provider, _, _, _ = _make_provider(novel_repo=novel_repo, series_repo=series_repo)

        result = await provider.assemble_series_history(current.id)

        assert result == ""


# ---------------------------------------------------------------------------
# assemble_series_history — series novel with prior bands
# ---------------------------------------------------------------------------


class TestAssembleSeriesNovel:
    """Series novel (band > 1) → non-empty history from prior bands."""

    @pytest.mark.asyncio
    async def test_prior_band_full_summary_appears(self) -> None:
        series_id = uuid.uuid4()
        band1 = _novel(series_id=series_id, position=1, title="The Beginning")
        band2 = _novel(series_id=series_id, position=2, title="The Vale")
        novel_repo = FakeNovelRepository()
        novel_repo.seed(band1, band2)
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(series_id), novels=[band1, band2])
        band_repo = FakeBandSummaryRepository()
        band_repo.seed(
            _band_summary(band1.id, full="The hero discovers the map.", short="A map is found.")
        )

        provider, _, _, _ = _make_provider(
            novel_repo=novel_repo, series_repo=series_repo, band_repo=band_repo
        )

        result = await provider.assemble_series_history(band2.id)

        assert "Previously in this series" in result
        assert "The hero discovers the map." in result
        assert "Band 1 — The Beginning" in result
        # Current band must never appear.
        assert "The Vale" not in result

    @pytest.mark.asyncio
    async def test_uses_context_window_size_from_settings(self) -> None:
        """context_window_size=0 → prior bands use only short summaries."""
        series_id = uuid.uuid4()
        band1 = _novel(series_id=series_id, position=1, title="B1")
        band2 = _novel(series_id=series_id, position=2, title="B2")
        novel_repo = FakeNovelRepository()
        novel_repo.seed(band1, band2)
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(series_id), novels=[band1, band2])
        # Force window to 0 → short summaries only.
        series_repo._settings[series_id] = SeriesSettings(
            series_id=series_id, author_voice=None, context_window_size=0
        )
        band_repo = FakeBandSummaryRepository()
        band_repo.seed(
            _band_summary(band1.id, full="FULL_TEXT", short="SHORT_TEXT"),
        )

        provider, _, _, _ = _make_provider(
            novel_repo=novel_repo, series_repo=series_repo, band_repo=band_repo
        )

        result = await provider.assemble_series_history(band2.id)

        assert "SHORT_TEXT" in result
        assert "FULL_TEXT" not in result  # window=0 → no full summaries

    @pytest.mark.asyncio
    async def test_missing_band_summary_skipped_not_crash(self) -> None:
        """A prior band with no summary row is skipped (RULE-11)."""
        series_id = uuid.uuid4()
        band1 = _novel(series_id=series_id, position=1, title="B1")
        band2 = _novel(series_id=series_id, position=2, title="B2")
        band3 = _novel(series_id=series_id, position=3, title="B3")
        novel_repo = FakeNovelRepository()
        novel_repo.seed(band1, band2, band3)
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(series_id), novels=[band1, band2, band3])
        band_repo = FakeBandSummaryRepository()
        # Only band 2 has a summary; band 1 has none.
        band_repo.seed(_band_summary(band2.id, full="Band two plot.", short="B2 short."))

        provider, _, _, _ = _make_provider(
            novel_repo=novel_repo, series_repo=series_repo, band_repo=band_repo
        )

        result = await provider.assemble_series_history(band3.id)

        assert "Band two plot." in result
        # Band 1 had no summary → contributes nothing, no crash.
        assert "B1" not in result.split("Band two plot.")[0]

    @pytest.mark.asyncio
    async def test_token_budget_default_applied(self) -> None:
        """The provider passes a token budget through to the tier."""
        series_id = uuid.uuid4()
        band1 = _novel(series_id=series_id, position=1, title="B1")
        band2 = _novel(series_id=series_id, position=2, title="B2")
        novel_repo = FakeNovelRepository()
        novel_repo.seed(band1, band2)
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(series_id), novels=[band1, band2])
        band_repo = FakeBandSummaryRepository()
        band_repo.seed(_band_summary(band1.id, full="Plot.", short="short."))

        provider, _, _, _ = _make_provider(
            novel_repo=novel_repo, series_repo=series_repo, band_repo=band_repo
        )

        # token_budget=0 → tier returns "" (nothing fits).
        result = await provider.assemble_series_history(band2.id, token_budget=0)

        assert result == ""


# ---------------------------------------------------------------------------
# KB-Redirect (Part A) — series vs standalone branch
# ---------------------------------------------------------------------------


class TestKBRedirect:
    """``resolve_kb_fetch_mode`` encodes the series-vs-standalone redirect.

    For series novels the canonical KB source is ``find_merged_for_novel``
    (Canon + Overlay); standalones keep the per-novel query. This is the
    Spec 2 §3.1 KB-Redirect decision, surfaced as a tested method so the
    wiring point is explicit and governed.
    """

    @pytest.mark.asyncio
    async def test_series_novel_uses_merged(self) -> None:
        series_id = uuid.uuid4()
        novel = _novel(series_id=series_id, position=2, title="Band Two")
        novel_repo = FakeNovelRepository()
        novel_repo.seed(novel)

        provider, _, _, _ = _make_provider(novel_repo=novel_repo)

        mode = await provider.resolve_kb_fetch_mode(novel.id)

        assert mode == "merged"

    @pytest.mark.asyncio
    async def test_standalone_novel_uses_per_novel(self) -> None:
        from narrare.novels.models import Novel

        novel = Novel()
        novel.id = uuid.uuid4()
        novel.user_id = uuid.uuid4()
        novel.title = "Standalone"
        novel.series_id = None
        novel.series_position = None
        novel_repo = FakeNovelRepository()
        novel_repo.seed(novel)

        provider, _, _, _ = _make_provider(novel_repo=novel_repo)

        mode = await provider.resolve_kb_fetch_mode(novel.id)

        assert mode == "per_novel"

    @pytest.mark.asyncio
    async def test_missing_novel_uses_per_novel_safe_default(self) -> None:
        provider, _, _, _ = _make_provider()

        mode = await provider.resolve_kb_fetch_mode(uuid.uuid4())

        # Unknown novel → safe per-novel default (never merged for a novel
        # we can't confirm is in a series).
        assert mode == "per_novel"


class TestDefaultTokenBudget:
    def test_provider_default_derives_from_core_constant(self) -> None:
        """ADR-082 inventory (a)2: the mirror constant must not drift from
        the Core default (the old 512/512 mirror pair was the defect)."""
        from narrare.series.series_history_provider import _DEFAULT_TOKEN_BUDGET
        from narrare_core.context.budget import DEFAULT_SERIES_HISTORY_BUDGET

        assert _DEFAULT_TOKEN_BUDGET == DEFAULT_SERIES_HISTORY_BUDGET


class TestCollectSeriesBandData:
    """C1: series-keyed band-data fetch with next-band semantics (ALL
    positioned members are prior bands — no position filtering, unlike
    assemble_series_history which filters below the current novel)."""

    @pytest.mark.asyncio
    async def test_returns_all_positioned_members_with_summaries(self) -> None:
        series_id = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        novel_row = _novel_row(series_id=series_id, position=1, title="Band 1")
        unpositioned = _novel_row(series_id=series_id, position=None, title="Draft")
        series_repo.seed(_series(series_id), novels=[novel_row, unpositioned])
        band_repo = FakeBandSummaryRepository()
        band_repo.seed(
            BandSummary(
                novel_id=novel_row.id,
                full_summary="Full summary.",
                short_summary="Short.",
            )
        )
        provider = SeriesHistoryProvider(
            novel_repo=FakeNovelRepository(),
            series_repo=series_repo,
            band_summary_repo=band_repo,
        )

        result = await provider.collect_series_band_data(series_id)

        assert len(result) == 1  # unpositioned member excluded
        assert result[0].position == 1
        assert result[0].title == "Band 1"
        assert result[0].full_summary == "Full summary."
        assert result[0].short_summary == "Short."

    @pytest.mark.asyncio
    async def test_member_without_summary_row_yields_none_texts(self) -> None:
        series_id = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        member = _novel_row(series_id=series_id, position=2)
        series_repo.seed(_series(series_id), novels=[member])
        provider = SeriesHistoryProvider(
            novel_repo=FakeNovelRepository(),
            series_repo=series_repo,
            band_summary_repo=FakeBandSummaryRepository(),
        )

        result = await provider.collect_series_band_data(series_id)

        assert result[0].full_summary is None
        assert result[0].short_summary is None
        assert result[0].override is None
