"""Tests for BetaReaderAgent — Phase 2 output parsing and score clamping.

Test strategy:
- TestModel for deterministic agent tests
- Output functions tested directly via _process_phase2
- No real LLM calls (RULE-01b)

Split from test_beta_reader_agent.py to stay under 200 lines (RULE-04).
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.beta_reader_processors import process_beta_reader_phase2
from narrare_core.agents.beta_reader_types import (
    BetaReaderDeps,
    BetaReaderPhase2Output,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_context(**overrides: object) -> RunContext[BetaReaderDeps]:
    """Create a RunContext with default BetaReaderDeps."""
    deps = BetaReaderDeps(**overrides)  # type: ignore[arg-type]
    return RunContext[BetaReaderDeps](deps=deps, model=TestModel(), usage=RunUsage())


# ---------------------------------------------------------------------------
# A. Phase 2 output parsing
# ---------------------------------------------------------------------------


class TestProcessPhase2:
    """_process_phase2 structures deep-dive response correctly."""

    @pytest.mark.asyncio
    async def test_partial_output_returns_defaults(self) -> None:
        """During streaming, returns empty Phase 2 output."""
        ctx = _make_run_context()
        ctx.partial_output = True

        result = await process_beta_reader_phase2(ctx)

        assert isinstance(result, BetaReaderPhase2Output)
        assert result.detailed_feedback == []
        assert result.revision_suggestions == []
        assert result.category_score == 5

    @pytest.mark.asyncio
    async def test_full_output_maps_correctly(self) -> None:
        """Full Phase 2 response maps correctly."""
        ctx = _make_run_context()

        result = await process_beta_reader_phase2(
            ctx,
            detailed_feedback=[
                {
                    "category": "character",
                    "severity": "critical",
                    "title": "Inconsistent motivation",
                    "description": "Character suddenly changes goal",
                },
            ],
            revision_suggestions=["Rewrite the dialogue on page 3"],
            category_score=4,
        )

        assert len(result.detailed_feedback) == 1
        assert result.detailed_feedback[0].severity == "critical"
        assert result.revision_suggestions == ["Rewrite the dialogue on page 3"]
        assert result.category_score == 4


# ---------------------------------------------------------------------------
# B. Score clamping (Phase 2)
# ---------------------------------------------------------------------------


class TestScoreClamping:
    """category_score is bounded to 1-10 in Phase 2."""

    @pytest.mark.asyncio
    async def test_score_below_minimum_clamped_to_1(self) -> None:
        """Score of 0 is clamped to 1."""
        ctx = _make_run_context()

        result = await process_beta_reader_phase2(ctx, category_score=0)

        assert result.category_score == 1

    @pytest.mark.asyncio
    async def test_score_above_maximum_clamped_to_10(self) -> None:
        """Score of 15 is clamped to 10."""
        ctx = _make_run_context()

        result = await process_beta_reader_phase2(ctx, category_score=15)

        assert result.category_score == 10

    @pytest.mark.asyncio
    async def test_negative_score_clamped_to_1(self) -> None:
        """Negative score is clamped to 1."""
        ctx = _make_run_context()

        result = await process_beta_reader_phase2(ctx, category_score=-5)

        assert result.category_score == 1
