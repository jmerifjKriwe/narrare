"""Tests for SeriesHistoryTier.preview (C1 — Context-Window Slider).

The preview must predict EXACTLY what :meth:`assemble` renders at a given
window size / token budget — same entry building, same greedy fit. The
consistency tests run both side by side and assert the prediction matches
the real output line for line. Pure data, no I/O (RULE-07).
"""

from __future__ import annotations

import pytest

from narrare_core.context.series_history import (
    _HEADER,  # pyright: ignore[reportPrivateUsage]
    BandSummaryData,
    SeriesHistoryPreview,
    SeriesHistoryTier,
    _estimate_tokens,  # pyright: ignore[reportPrivateUsage]
)


def _band(
    position: int,
    *,
    title: str = "Untitled",
    full: str | None = None,
    short: str | None = None,
    override: str | None = None,
) -> BandSummaryData:
    return BandSummaryData(
        position=position,
        title=title,
        full_summary=full,
        short_summary=short,
        override=override,
    )


def _long(tag: str, chars: int = 1500) -> str:
    """~375+ tokens of text with unique start/end markers."""
    return f"{tag}START " + ("x" * chars) + f" {tag}END"


def _four_bands() -> list[BandSummaryData]:
    return [
        _band(1, full=_long("B1"), short="One.", title="First"),
        _band(2, full=_long("B2"), short="Two.", title="Second"),
        _band(3, full=_long("B3"), short="Three.", title="Third"),
        _band(4, full=_long("B4"), short="Four.", title="Fourth"),
    ]


class TestFullShortClassification:
    async def test_window_two_full_recent_short_older(self) -> None:
        result = await SeriesHistoryTier().preview(_four_bands(), 2, 100_000)

        assert result.bands_total == 4
        assert result.bands_full == 2  # bands 4, 3 (newest)
        assert result.bands_short == 2  # bands 2, 1
        assert result.bands_truncated == 0
        assert result.bands_dropped == 0
        assert result.bands_missing == 0
        assert result.budget_clipped is False

    async def test_window_larger_than_band_count_treats_all_full(self) -> None:
        result = await SeriesHistoryTier().preview(_four_bands(), 10, 100_000)

        assert result.bands_full == 4
        assert result.bands_short == 0

    async def test_override_counts_as_full_within_window(self) -> None:
        bands = [
            _band(1, full=_long("B1"), short="One."),
            _band(2, full=None, short="Two.", override="Curated."),
        ]
        result = await SeriesHistoryTier().preview(bands, 1, 100_000)

        assert result.bands_full == 1  # band 2 via override
        assert result.bands_short == 1

    async def test_missing_summaries_depend_on_window(self) -> None:
        """A band without full summary is missing in-window, but its short
        summary still counts out-of-window (mirrors _select_text)."""
        bands = [_band(1, full=None, short="One."), _band(2, full=_long("B2"), short="Two.")]
        tier = SeriesHistoryTier()

        large = await tier.preview(bands, 5, 100_000)
        small = await tier.preview(bands, 1, 100_000)

        assert large.bands_missing == 1  # band 1 has no full text
        assert small.bands_missing == 0  # band 1 out of window -> short used


class TestBudgetClipping:
    async def test_boundary_band_truncated_older_dropped(self) -> None:
        """Budget fits band 4 fully + a slice of band 3 -> band 3 truncated,
        bands 2 and 1 dropped (sacrifice older first)."""
        tier = SeriesHistoryTier()
        band4 = f"Band 4 — Fourth: {_long('B4')}"
        budget = _estimate_tokens(band4) + 200  # room for band 4 + a 200-tok slice

        result = await tier.preview(_four_bands(), 4, budget)

        assert result.bands_full == 1
        assert result.bands_truncated == 1
        assert result.bands_dropped == 2
        assert result.budget_clipped is True

    async def test_budget_below_truncate_floor_drops_without_truncating(self) -> None:
        """Remaining headroom < _MIN_TRUNCATE_TOKENS -> nothing appended.

        Budget 25: 25 - _HEADER (7 tokens) = 18 < 20, so the boundary band
        is dropped whole. Budget 30 must NOT be used here: 30 - 7 = 23 >= 20
        puts the boundary band into the truncation band (exactly the
        consistency suite's budget=30 parametrization below), which would
        contradict the drop-expectation.
        """
        result = await SeriesHistoryTier().preview(_four_bands(), 4, 25)

        assert result.bands_full == 0
        assert result.bands_truncated == 0
        assert result.bands_dropped == 4
        assert result.budget_clipped is True

    async def test_zero_budget_drops_everything(self) -> None:
        result = await SeriesHistoryTier().preview(_four_bands(), 3, 0)

        assert result.estimated_tokens == 0
        assert result.bands_dropped == 4

    async def test_estimated_tokens_never_exceed_budget(self) -> None:
        tier = SeriesHistoryTier()
        for budget in (0, 30, 200, 800, 2_000, 100_000):
            result = await tier.preview(_four_bands(), 4, budget)
            assert result.estimated_tokens <= max(budget, 0), budget


class TestEdgeCases:
    async def test_empty_bands_all_zero(self) -> None:
        result = await SeriesHistoryTier().preview([], 3, 16_000)

        assert result == SeriesHistoryPreview(
            window_size=3,
            token_budget=16_000,
            estimated_tokens=0,
            bands_total=0,
            bands_full=0,
            bands_short=0,
            bands_truncated=0,
            bands_dropped=0,
            bands_missing=0,
            budget_clipped=False,
        )

    async def test_window_size_reported_clamped_at_zero(self) -> None:
        """Negative window mirrors assemble's max(window, 0) treatment."""
        result = await SeriesHistoryTier().preview(_four_bands(), -1, 100_000)

        assert result.window_size == 0
        assert result.bands_full == 0
        assert result.bands_short == 4


class TestAssembleConsistency:
    """The preview predicts assemble's real output — the no-second-algorithm
    guarantee, asserted end to end."""

    @pytest.mark.parametrize("window_size", [0, 1, 2, 3, 4, 7])
    @pytest.mark.parametrize("token_budget", [0, 30, 200, 800, 2_000, 100_000])
    async def test_preview_matches_assemble_output(
        self, window_size: int, token_budget: int
    ) -> None:
        tier = SeriesHistoryTier()
        bands = [*_four_bands(), _band(5, full=None, short=None)]  # one fully-missing band

        preview = await tier.preview(bands, window_size, token_budget)
        output = await tier.assemble(bands, window_size, token_budget)

        rendered_lines = sum(1 for line in output.split("\n\n") if line.startswith("Band "))
        rendered = preview.bands_full + preview.bands_short + preview.bands_truncated
        assert rendered_lines == rendered
        if rendered > 0:
            assert output.startswith(_HEADER)
            assert preview.estimated_tokens == _estimate_tokens(output)
        else:
            assert output == ""
            assert preview.estimated_tokens == 0

    @pytest.mark.parametrize("window_size", [1, 3, 5])
    @pytest.mark.parametrize("token_budget", [30, 800, 100_000])
    async def test_classification_invariant(self, window_size: int, token_budget: int) -> None:
        result = await SeriesHistoryTier().preview(_four_bands(), window_size, token_budget)

        assert (
            result.bands_full
            + result.bands_short
            + result.bands_truncated
            + result.bands_dropped
            + result.bands_missing
            == result.bands_total
            == 4
        )
        assert result.budget_clipped == (result.bands_truncated + result.bands_dropped > 0)
