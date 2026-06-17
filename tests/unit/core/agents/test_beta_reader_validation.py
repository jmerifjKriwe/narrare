"""Tests for BetaReaderAgent output validators — ADR-035.

Tests the deterministic invariants enforced by _validate_phase1 and _validate_phase2:

Phase 1:
- Each strength/feedback/question should have non-empty content
- category should be from known set (plot/character/prose/pacing/experience)

Phase 2:
- category_score clamped 1-10
- revision_suggestions should have non-empty strings

Test strategy:
- Call validators directly with mocked RunContext
- No real LLM calls (RULE-01b)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.beta_reader_types import (
    AgentDeepDiveFeedback,
    AgentFeedbackItem,
    AgentOverallAssessment,
    AgentReaderQuestion,
    AgentStrength,
    BetaReaderDeps,
    BetaReaderPhase1Output,
    BetaReaderPhase2Output,
)
from narrare_core.agents.beta_reader_validators import (
    validate_beta_reader_phase1,
    validate_beta_reader_phase2,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ctx() -> RunContext[BetaReaderDeps]:
    return RunContext[BetaReaderDeps](
        deps=BetaReaderDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _make_overall() -> AgentOverallAssessment:
    return AgentOverallAssessment(
        summary="Good chapter overall.",
        reader_engagement=7,
        emotional_impact=6,
        pacing_score=5,
        prose_quality=7,
        plot_progression=6,
        character_development=5,
    )


def _valid_phase1(**overrides: object) -> BetaReaderPhase1Output:
    """Build a valid Phase 1 output for testing."""
    defaults: dict[str, object] = {
        "strengths": [
            AgentStrength(
                category="plot", title="Strong opening", description="Hook is effective."
            ),
        ],
        "feedback": [
            AgentFeedbackItem(
                category="pacing",
                severity="moderate",
                title="Slow middle",
                description="The middle section drags.",
            ),
        ],
        "questions": [
            AgentReaderQuestion(category="character", question="Why does Alice trust Bob?"),
        ],
        "overall": _make_overall(),
    }
    defaults.update(overrides)
    return BetaReaderPhase1Output(**defaults)  # type: ignore[arg-type]


def _valid_phase2(**overrides: object) -> BetaReaderPhase2Output:
    """Build a valid Phase 2 output for testing."""
    defaults: dict[str, object] = {
        "detailed_feedback": [
            AgentDeepDiveFeedback(
                category="character",
                severity="moderate",
                title="Flat character",
                description="Bob lacks depth.",
            ),
        ],
        "revision_suggestions": ["Add more backstory for Bob."],
        "category_score": 6,
    }
    defaults.update(overrides)
    return BetaReaderPhase2Output(**defaults)  # type: ignore[arg-type]


# ===========================================================================
# Phase 1 Tests
# ===========================================================================


class TestPhase1ValidOutputPasses:
    """Valid Phase 1 output passes the validator."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(self, ctx: RunContext[BetaReaderDeps]) -> None:
        output = _valid_phase1()
        result = await validate_beta_reader_phase1(ctx, output)
        assert len(result.strengths) == 1
        assert len(result.feedback) == 1

    @pytest.mark.asyncio
    async def test_empty_lists_pass(self, ctx: RunContext[BetaReaderDeps]) -> None:
        output = _valid_phase1(
            strengths=[],
            feedback=[],
            questions=[],
            overall=_make_overall(),
        )
        result = await validate_beta_reader_phase1(ctx, output)
        assert result.strengths == []


class TestPhase1FilterEmptyContent:
    """Items with empty content are filtered."""

    @pytest.mark.asyncio
    async def test_filter_empty_title_strength(self, ctx: RunContext[BetaReaderDeps]) -> None:
        output = _valid_phase1(
            strengths=[
                AgentStrength(category="plot", title="", description="Has desc"),
                AgentStrength(category="plot", title="Valid", description="Valid desc"),
            ],
        )
        result = await validate_beta_reader_phase1(ctx, output)
        assert len(result.strengths) == 1

    @pytest.mark.asyncio
    async def test_filter_empty_description_strength(self, ctx: RunContext[BetaReaderDeps]) -> None:
        output = _valid_phase1(
            strengths=[
                AgentStrength(category="plot", title="Has title", description=""),
                AgentStrength(category="plot", title="Valid", description="Valid desc"),
            ],
        )
        result = await validate_beta_reader_phase1(ctx, output)
        assert len(result.strengths) == 1

    @pytest.mark.asyncio
    async def test_filter_empty_question(self, ctx: RunContext[BetaReaderDeps]) -> None:
        output = _valid_phase1(
            questions=[
                AgentReaderQuestion(category="plot", question=""),
                AgentReaderQuestion(category="plot", question="Valid question?"),
            ],
        )
        result = await validate_beta_reader_phase1(ctx, output)
        assert len(result.questions) == 1


class TestPhase1InvalidCategory:
    """Invalid categories raise ModelRetry."""

    @pytest.mark.asyncio
    async def test_invalid_feedback_category_raises(self, ctx: RunContext[BetaReaderDeps]) -> None:
        output = _valid_phase1(
            feedback=[
                AgentFeedbackItem(
                    category="invalid_category",
                    severity="moderate",
                    title="Issue",
                    description="Some desc",
                ),
            ],
        )
        with pytest.raises(ModelRetry, match="not valid"):
            await validate_beta_reader_phase1(ctx, output)

    @pytest.mark.asyncio
    async def test_valid_categories_pass(self, ctx: RunContext[BetaReaderDeps]) -> None:
        for cat in ("plot", "character", "prose", "pacing", "experience"):
            output = _valid_phase1(
                feedback=[
                    AgentFeedbackItem(
                        category=cat,
                        severity="moderate",
                        title="Issue",
                        description="Some desc",
                    ),
                ],
            )
            result = await validate_beta_reader_phase1(ctx, output)
            assert result.feedback[0].category == cat


# ===========================================================================
# Phase 2 Tests
# ===========================================================================


class TestPhase2ValidOutputPasses:
    """Valid Phase 2 output passes the validator."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(self, ctx: RunContext[BetaReaderDeps]) -> None:
        output = _valid_phase2()
        result = await validate_beta_reader_phase2(ctx, output)
        assert len(result.detailed_feedback) == 1
        assert result.category_score == 6


class TestPhase2FilterEmptySuggestions:
    """Empty revision suggestions are filtered."""

    @pytest.mark.asyncio
    async def test_filter_empty_suggestions(self, ctx: RunContext[BetaReaderDeps]) -> None:
        output = _valid_phase2(
            revision_suggestions=["Valid", "", "   ", "Also valid"],
        )
        result = await validate_beta_reader_phase2(ctx, output)
        assert result.revision_suggestions == ["Valid", "Also valid"]


class TestPhase2CategoryScoreClamping:
    """category_score is clamped to 1-10."""

    @pytest.mark.asyncio
    async def test_clamp_below_one(self, ctx: RunContext[BetaReaderDeps]) -> None:
        output = _valid_phase2()
        output = output.model_copy(update={"category_score": 0})
        result = await validate_beta_reader_phase2(ctx, output)
        assert result.category_score == 1

    @pytest.mark.asyncio
    async def test_clamp_above_ten(self, ctx: RunContext[BetaReaderDeps]) -> None:
        output = _valid_phase2()
        output = output.model_copy(update={"category_score": 15})
        result = await validate_beta_reader_phase2(ctx, output)
        assert result.category_score == 10


# ===========================================================================
# Determinism
# ===========================================================================


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_phase1(self, ctx: RunContext[BetaReaderDeps]) -> None:
        output = _valid_phase1()
        result1 = await validate_beta_reader_phase1(ctx, output)
        result2 = await validate_beta_reader_phase1(ctx, output)
        assert len(result1.strengths) == len(result2.strengths)

    @pytest.mark.asyncio
    async def test_deterministic_phase2(self, ctx: RunContext[BetaReaderDeps]) -> None:
        output = _valid_phase2()
        result1 = await validate_beta_reader_phase2(ctx, output)
        result2 = await validate_beta_reader_phase2(ctx, output)
        assert result1.category_score == result2.category_score

    @pytest.mark.asyncio
    async def test_deterministic_phase1_retry(self, ctx: RunContext[BetaReaderDeps]) -> None:
        output = _valid_phase1(
            feedback=[
                AgentFeedbackItem(
                    category="bad_cat",
                    severity="moderate",
                    title="Issue",
                    description="Some desc",
                ),
            ],
        )
        for _ in range(3):
            with pytest.raises(ModelRetry, match="not valid"):
                await validate_beta_reader_phase1(ctx, output)
