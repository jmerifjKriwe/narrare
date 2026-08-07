"""Tests for SeriesHistoryTier + BandSummaryData (Spec 2, Task 6).

Validates the series-history context tier: recency-window selection
(full vs short summary), override precedence, token-budget truncation
(keep most recent, truncate/drop older), graceful degradation for all
edge cases, and output format.

The tier is pure formatting + truncation — it receives pre-fetched
``BandSummaryData`` and never touches the DB (RULE-07: Core has zero
Backend imports). These tests therefore need no fakes, only data.
"""

from __future__ import annotations

import pytest

from narrare_core.context.series_history import BandSummaryData, SeriesHistoryTier

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _band(
    position: int,
    *,
    title: str = "Untitled",
    full: str | None = None,
    short: str | None = None,
    override: str | None = None,
) -> BandSummaryData:
    """Build a BandSummaryData with concise kwargs."""
    return BandSummaryData(
        position=position,
        title=title,
        full_summary=full,
        short_summary=short,
        override=override,
    )


def _long(tag: str, chars: int = 1500) -> str:
    """Build a long summary with a unique start + end marker around filler.

    The markers let truncation tests assert presence of the start and
    absence of the end unambiguously.
    """
    return f"{tag}START " + ("x" * chars) + f" {tag}END"


# ---------------------------------------------------------------------------
# BandSummaryData dataclass
# ---------------------------------------------------------------------------


class TestBandSummaryData:
    """The cross-boundary value type passed from Backend into Core."""

    def test_construction_stores_all_fields(self) -> None:
        d = BandSummaryData(
            position=2,
            title="The Vale",
            full_summary="full",
            short_summary="short",
            override=None,
        )
        assert d.position == 2
        assert d.title == "The Vale"
        assert d.full_summary == "full"
        assert d.short_summary == "short"
        assert d.override is None

    def test_is_frozen(self) -> None:
        """Frozen dataclass — matches EntityMetadata/Suggestion convention."""
        d = _band(1, full="f")
        with pytest.raises(AttributeError):
            d.position = 5  # type: ignore[misc]

    def test_allows_none_summaries(self) -> None:
        d = BandSummaryData(position=1, title="t")
        assert d.full_summary is None
        assert d.short_summary is None
        assert d.override is None


# ---------------------------------------------------------------------------
# Recency-window logic
# ---------------------------------------------------------------------------


class TestRecencyWindow:
    """Last `window_size` bands use full_summary; older bands use short."""

    async def test_last_window_bands_use_full_older_use_short(self) -> None:
        """5 bands, window=2 → bands 4,5 full; bands 1,2,3 short."""
        bands = [
            _band(1, full="F1", short="S1"),
            _band(2, full="F2", short="S2"),
            _band(3, full="F3", short="S3"),
            _band(4, full="F4", short="S4"),
            _band(5, full="F5", short="S5"),
        ]
        tier = SeriesHistoryTier()
        result = await tier.assemble(bands=bands, window_size=2, token_budget=10_000)

        assert "F4" in result
        assert "F5" in result
        assert "S1" in result
        assert "S2" in result
        assert "S3" in result
        # Older bands must NOT contribute their full summary.
        assert "F1" not in result
        assert "F2" not in result
        assert "F3" not in result

    async def test_window_size_zero_uses_short_for_all(self) -> None:
        bands = [_band(1, full="F1", short="S1"), _band(2, full="F2", short="S2")]
        tier = SeriesHistoryTier()
        result = await tier.assemble(bands=bands, window_size=0, token_budget=10_000)

        assert "S1" in result
        assert "S2" in result
        assert "F1" not in result
        assert "F2" not in result

    async def test_window_larger_than_band_count_uses_full_for_all(self) -> None:
        bands = [_band(1, full="F1", short="S1"), _band(2, full="F2", short="S2")]
        tier = SeriesHistoryTier()
        result = await tier.assemble(bands=bands, window_size=99, token_budget=10_000)

        assert "F1" in result
        assert "F2" in result
        assert "S1" not in result
        assert "S2" not in result


# ---------------------------------------------------------------------------
# Override preference
# ---------------------------------------------------------------------------


class TestOverridePreference:
    """`override or full_summary` within the recency window."""

    async def test_override_takes_precedence_over_full(self) -> None:
        bands = [_band(1, full="AUTO_FULL", short="S1", override="CURATED")]
        tier = SeriesHistoryTier()
        result = await tier.assemble(bands=bands, window_size=1, token_budget=10_000)

        assert "CURATED" in result
        assert "AUTO_FULL" not in result

    async def test_empty_override_falls_back_to_full(self) -> None:
        """Empty-string override is falsy → use full_summary."""
        bands = [_band(1, full="AUTO_FULL", short="S1", override="")]
        tier = SeriesHistoryTier()
        result = await tier.assemble(bands=bands, window_size=1, token_budget=10_000)

        assert "AUTO_FULL" in result

    async def test_override_not_applied_outside_window(self) -> None:
        """Outside the window, short_summary wins; override is ignored."""
        bands = [
            _band(1, full="F1", short="S1", override="O1"),
            _band(2, full="F2", short="S2"),
        ]
        tier = SeriesHistoryTier()
        # window=1 → only band 2 (most recent) is in window.
        result = await tier.assemble(bands=bands, window_size=1, token_budget=10_000)

        assert "S1" in result  # band 1 rendered via short
        assert "O1" not in result  # override ignored outside window
        assert "F1" not in result


# ---------------------------------------------------------------------------
# Graceful degradation (RULE-11)
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Every edge case returns a sane value, never crashes."""

    async def test_empty_bands_returns_empty_string(self) -> None:
        tier = SeriesHistoryTier()
        result = await tier.assemble(bands=[], window_size=3, token_budget=512)
        assert result == ""

    async def test_all_summaries_missing_returns_empty_string(self) -> None:
        """A band with no full/short/override contributes nothing."""
        bands = [_band(1), _band(2)]
        tier = SeriesHistoryTier()
        result = await tier.assemble(bands=bands, window_size=3, token_budget=512)
        assert result == ""

    async def test_in_window_band_with_no_full_or_override_skipped(self) -> None:
        """In-window band missing full+override is skipped, others kept."""
        bands = [
            _band(1, full=None, short="S1", override=None),  # in window, no full
            _band(2, full="F2", short="S2"),
        ]
        tier = SeriesHistoryTier()
        result = await tier.assemble(bands=bands, window_size=5, token_budget=10_000)

        # Band 1 has no full/override → skipped entirely (no fallback to short).
        assert "S1" not in result
        assert "F2" in result

    async def test_out_of_window_band_with_no_short_skipped(self) -> None:
        bands = [
            _band(1, full="F1", short=None),  # older, no short → skipped
            _band(2, full="F2", short="S2"),
            _band(3, full="F3", short="S3"),
        ]
        tier = SeriesHistoryTier()
        # window=2 → band 1 is outside; has no short → skipped.
        result = await tier.assemble(bands=bands, window_size=2, token_budget=10_000)

        assert "F1" not in result
        assert "F3" in result
        assert "F2" in result

    async def test_token_budget_zero_returns_empty_string(self) -> None:
        bands = [_band(1, full="F1", short="S1")]
        tier = SeriesHistoryTier()
        result = await tier.assemble(bands=bands, window_size=3, token_budget=0)
        assert result == ""

    async def test_token_budget_negative_returns_empty_string(self) -> None:
        bands = [_band(1, full="F1", short="S1")]
        tier = SeriesHistoryTier()
        result = await tier.assemble(bands=bands, window_size=3, token_budget=-5)
        assert result == ""

    async def test_no_lone_header_when_nothing_fits(self) -> None:
        """Never emit 'Previously in this series:' with no body."""
        bands = [_band(1, full="F1", short="S1")]
        tier = SeriesHistoryTier()
        result = await tier.assemble(bands=bands, window_size=3, token_budget=1)
        assert result == ""
        assert "Previously in this series" not in result


# ---------------------------------------------------------------------------
# Token-budget truncation (keep most recent, truncate/drop older)
# ---------------------------------------------------------------------------


class TestTokenBudgetTruncation:
    """When total exceeds budget, older bands are sacrificed first."""

    async def test_drops_oldest_keeps_only_most_recent(self) -> None:
        """Budget for ~1 band → only the most-recent band survives."""
        bands = [
            _band(1, full=_long("B1"), short="S1"),
            _band(2, full=_long("B2"), short="S2"),
            _band(3, full=_long("B3"), short="S3"),
        ]
        tier = SeriesHistoryTier()
        # Each full entry is ~383 tokens; header ~7. Budget=400 → band 3 fits,
        # only ~10 tokens remain (< 20-token truncation floor) → older dropped.
        result = await tier.assemble(bands=bands, window_size=3, token_budget=400)

        assert "B3START" in result
        assert "B3END" in result  # band 3 complete
        assert "B2START" not in result
        assert "B1START" not in result

    async def test_keeps_two_most_recent_drops_oldest(self) -> None:
        bands = [
            _band(1, full=_long("B1"), short="S1"),
            _band(2, full=_long("B2"), short="S2"),
            _band(3, full=_long("B3"), short="S3"),
        ]
        tier = SeriesHistoryTier()
        # Budget for ~2 bands (7 + 383 + 383 = 773); 780 leaves <20 → 3rd dropped.
        result = await tier.assemble(bands=bands, window_size=3, token_budget=780)

        assert "B3START" in result and "B3END" in result
        assert "B2START" in result and "B2END" in result
        # Oldest band dropped entirely.
        assert "B1START" not in result
        assert "B1END" not in result

    async def test_truncates_boundary_band_to_remaining_budget(self) -> None:
        """When one band fits fully + a little room, the next is truncated."""
        bands = [
            _band(1, full=_long("B1"), short="S1"),
            _band(2, full=_long("B2"), short="S2"),
            _band(3, full=_long("B3"), short="S3"),
        ]
        tier = SeriesHistoryTier()
        # Budget for 2 full bands + a truncated slice of the 3rd (oldest).
        result = await tier.assemble(bands=bands, window_size=3, token_budget=860)

        assert "B3START" in result and "B3END" in result
        assert "B2START" in result and "B2END" in result
        # Boundary band: start present, end cut off by truncation.
        assert "B1START" in result
        assert "B1END" not in result


# ---------------------------------------------------------------------------
# Format & ordering
# ---------------------------------------------------------------------------


class TestFormatAndOrdering:
    """Output shape: header, 'Band N — Title: text', newest first."""

    async def test_header_present_and_format(self) -> None:
        bands = [_band(1, full="The full plot.", short="One sentence.")]
        tier = SeriesHistoryTier()
        result = await tier.assemble(bands=bands, window_size=1, token_budget=10_000)

        assert result.startswith("Previously in this series:\n\n")
        assert "Band 1 — Untitled: The full plot." in result

    async def test_bands_ordered_newest_first(self) -> None:
        """Regardless of input order, output lists highest position first."""
        bands = [
            _band(1, full="F1", short="S1"),
            _band(3, full="F3", short="S3"),
            _band(2, full="F2", short="S2"),
        ]
        tier = SeriesHistoryTier()
        result = await tier.assemble(bands=bands, window_size=3, token_budget=10_000)

        pos1 = result.index("Band 3")
        pos2 = result.index("Band 2")
        pos3 = result.index("Band 1")
        assert pos1 < pos2 < pos3

    async def test_short_summary_used_outside_window_in_format(self) -> None:
        bands = [
            _band(1, full="FULL_ONE", short="SHORT_ONE"),
            _band(2, full="FULL_TWO", short="SHORT_TWO"),
        ]
        tier = SeriesHistoryTier()
        result = await tier.assemble(bands=bands, window_size=1, token_budget=10_000)

        # Band 2 (in window) → full; Band 1 (outside) → short.
        assert "Band 2 — Untitled: FULL_TWO" in result
        assert "Band 1 — Untitled: SHORT_ONE" in result


# ---------------------------------------------------------------------------
# Truncation helper behaviours
# ---------------------------------------------------------------------------


class TestTruncationHelpers:
    """Direct behavioural checks for the token-truncation internals.

    These exercise the defensive guards (zero/negative budget, already-fit
    text) that the end-to-end truncation tests reach only indirectly.
    """

    async def test_short_entry_within_budget_is_not_truncated(self) -> None:
        """An entry that already fits its headroom is returned verbatim."""
        bands = [_band(1, full="A short summary.", short="Short.")]
        tier = SeriesHistoryTier()
        result = await tier.assemble(bands=bands, window_size=1, token_budget=10_000)

        assert "A short summary." in result
        assert "…" not in result  # no truncation marker

    async def test_truncate_with_zero_remaining_drops_band(self) -> None:
        """When headroom is exactly 0, the boundary band is dropped, not
        truncated — confirmed end-to-end via a budget that leaves no room."""
        bands = [
            _band(1, full=_long("B1"), short="S1"),
            _band(2, full=_long("B2"), short="S2"),
        ]
        tier = SeriesHistoryTier()
        # Budget for header (7) + band 2 (383) = 390 exactly → 0 remaining.
        result = await tier.assemble(bands=bands, window_size=2, token_budget=390)

        assert "B2START" in result and "B2END" in result
        assert "B1START" not in result  # no headroom → dropped, not truncated
