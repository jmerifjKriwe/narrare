"""Unit tests for AIRemapService — coverage, confidence, and chapter role analysis.

Test-Strategie:
- Coverage und Confidence sind reine Mathematik (keine Mocks nötig)
- analyze_chapter_role testet mit/ohne Agent, empty summary
- Keine echten LLM-Calls (RULE-01b)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from narrare_core.agents.summary_types import SummaryOutput
from narrare_core.planning.remap import AIRemapService


@pytest.fixture()
def remap() -> AIRemapService:
    return AIRemapService()


# =====================================================================
# Coverage Threshold
# =====================================================================


class TestMeetsCoverageThreshold:
    def test_above_threshold(self, remap: AIRemapService) -> None:
        assert remap.meets_coverage_threshold(total_chapters=10, chapters_with_summaries=8) is True

    def test_at_threshold(self, remap: AIRemapService) -> None:
        assert remap.meets_coverage_threshold(total_chapters=10, chapters_with_summaries=5) is True

    def test_below_threshold(self, remap: AIRemapService) -> None:
        assert remap.meets_coverage_threshold(total_chapters=10, chapters_with_summaries=4) is False

    def test_zero_chapters(self, remap: AIRemapService) -> None:
        assert remap.meets_coverage_threshold(total_chapters=0, chapters_with_summaries=0) is False

    def test_custom_threshold(self, remap: AIRemapService) -> None:
        assert (
            remap.meets_coverage_threshold(
                total_chapters=10, chapters_with_summaries=3, threshold=0.3
            )
            is True
        )

    def test_custom_threshold_below(self, remap: AIRemapService) -> None:
        assert (
            remap.meets_coverage_threshold(
                total_chapters=10, chapters_with_summaries=2, threshold=0.3
            )
            is False
        )

    def test_default_constant(self) -> None:
        assert AIRemapService.DEFAULT_COVERAGE_THRESHOLD == 0.5


# =====================================================================
# Confidence Calculation
# =====================================================================


class TestCalculateConfidence:
    def test_full_coverage(self, remap: AIRemapService) -> None:
        assert remap.calculate_confidence(total_chapters=10, chapters_with_summaries=10) == 1.0

    def test_partial_coverage(self, remap: AIRemapService) -> None:
        assert remap.calculate_confidence(total_chapters=10, chapters_with_summaries=6) == 0.5

    def test_partial_at_threshold(self, remap: AIRemapService) -> None:
        assert remap.calculate_confidence(total_chapters=10, chapters_with_summaries=5) == 0.5

    def test_low_coverage(self, remap: AIRemapService) -> None:
        assert remap.calculate_confidence(total_chapters=10, chapters_with_summaries=4) == 0.0

    def test_no_summaries(self, remap: AIRemapService) -> None:
        assert remap.calculate_confidence(total_chapters=10, chapters_with_summaries=0) == 0.0

    def test_zero_chapters(self, remap: AIRemapService) -> None:
        assert remap.calculate_confidence(total_chapters=0, chapters_with_summaries=0) == 0.0


# =====================================================================
# Chapter Role Analysis
# =====================================================================


class TestAnalyzeChapterRole:
    @pytest.mark.asyncio
    async def test_empty_summary_returns_empty_string(self, remap: AIRemapService) -> None:
        result = await remap.analyze_chapter_role(summary="", structure_type="three_act")
        assert result == ""

    @pytest.mark.asyncio
    async def test_whitespace_summary_returns_empty_string(self, remap: AIRemapService) -> None:
        result = await remap.analyze_chapter_role(summary="   ", structure_type="five_act")
        assert result == ""

    @pytest.mark.asyncio
    async def test_without_agent_returns_empty_string(self, remap: AIRemapService) -> None:
        result = await remap.analyze_chapter_role(
            summary="The hero enters the forest.",
            structure_type="three_act",
            agent=None,
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_with_agent_returns_stage(self, remap: AIRemapService) -> None:
        """Mit gemocktem Agent der ein SummaryOutput zurückgibt."""
        mock_agent = AsyncMock()
        mock_output = SummaryOutput(summary="act-1")
        mock_agent.run = AsyncMock(return_value=mock_output)
        result = await remap.analyze_chapter_role(
            summary="The hero begins their journey.",
            structure_type="three_act",
            agent=mock_agent,
        )
        assert result == "act-1"

    @pytest.mark.asyncio
    async def test_with_agent_whitespace_stage(self, remap: AIRemapService) -> None:
        """Wenn der Agent leeren Text zurückgibt, wird "" retourniert."""
        mock_agent = AsyncMock()
        mock_output = SummaryOutput(summary="  ")
        mock_agent.run = AsyncMock(return_value=mock_output)
        result = await remap.analyze_chapter_role(
            summary="The hero begins.",
            structure_type="three_act",
            agent=mock_agent,
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_with_agent_error_returns_empty_string(self, remap: AIRemapService) -> None:
        """Bei Agent-Fehler wird "" retourniert (Graceful Degradation)."""
        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        result = await remap.analyze_chapter_role(
            summary="The hero begins.",
            structure_type="three_act",
            agent=mock_agent,
        )
        assert result == ""
