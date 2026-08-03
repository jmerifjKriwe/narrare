"""Tests für BandSummaryTypes — BandSummaryOutput + BandSummaryDeps.

Pure data-contract tests for the type layer of BandSummaryAgent (SERIES-002 /
Spec 2 Task 2). Agent behaviour tests live in ``test_band_summary_agent.py``.
"""

from __future__ import annotations

from narrare_core.agents.band_summary_types import BandSummaryDeps, BandSummaryOutput

# ---------------------------------------------------------------------------
# A. BandSummaryOutput
# ---------------------------------------------------------------------------


class TestBandSummaryOutput:
    """BandSummaryOutput validiert korrekt."""

    def test_defaults(self) -> None:
        output = BandSummaryOutput()
        assert output.full_summary == ""
        assert output.short_summary == ""

    def test_with_values(self) -> None:
        output = BandSummaryOutput(
            full_summary="The hero rises. Darkness falls. The kingdom is saved.",
            short_summary="A hero saves the kingdom from darkness.",
        )
        assert output.full_summary == "The hero rises. Darkness falls. The kingdom is saved."
        assert output.short_summary == "A hero saves the kingdom from darkness."

    def test_serialization(self) -> None:
        data = BandSummaryOutput(
            full_summary="Full plot summary.", short_summary="Short one-liner."
        ).model_dump()
        assert data["full_summary"] == "Full plot summary."
        assert data["short_summary"] == "Short one-liner."


# ---------------------------------------------------------------------------
# B. BandSummaryDeps
# ---------------------------------------------------------------------------


class TestBandSummaryDeps:
    """BandSummaryDeps erzeugt und konfiguriert korrekt."""

    def test_defaults(self) -> None:
        deps = BandSummaryDeps()
        assert deps.novel_title == ""
        assert deps.genre == ""
        assert deps.chapter_summaries == []

    def test_custom_values(self) -> None:
        deps = BandSummaryDeps(
            novel_title="The Forbidden Vale",
            genre="Fantasy",
            chapter_summaries=[
                "Chapter 1: The hero arrives.",
                "Chapter 2: A dark secret is revealed.",
            ],
        )
        assert deps.novel_title == "The Forbidden Vale"
        assert deps.genre == "Fantasy"
        assert len(deps.chapter_summaries) == 2
        assert deps.chapter_summaries[0] == "Chapter 1: The hero arrives."

    def test_chapter_summaries_is_a_copy(self) -> None:
        """Deps must not retain a reference to the caller's list (defensive copy)."""
        source = ["Summary A", "Summary B"]
        deps = BandSummaryDeps(chapter_summaries=source)
        source.append("Summary C")
        assert len(deps.chapter_summaries) == 2
