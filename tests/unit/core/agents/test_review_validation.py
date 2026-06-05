"""Tests for ReviewAgent output validator — ADR-035.

Tests the deterministic invariants enforced by _validate_output:
- quality_score must be 1-10 (enforce bounds)
- feedback must be non-empty
- When approved is False, issues must be non-empty
- Filter empty strings from suggestions and issues lists

Test strategy:
- Call _validate_output directly with mocked RunContext
- No real LLM calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.review_agent import ReviewAgent, ReviewDeps
from narrare_core.agents.review_types import ReviewOutput

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> ReviewAgent:
    return ReviewAgent(model=TestModel())


@pytest.fixture()
def ctx() -> RunContext[ReviewDeps]:
    return RunContext[ReviewDeps](
        deps=ReviewDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _valid_output(**overrides: object) -> ReviewOutput:
    """Build a valid ReviewOutput for testing."""
    defaults: dict[str, object] = {
        "approved": True,
        "feedback": "Good draft with strong prose.",
        "suggestions": ["Consider trimming the opening."],
        "quality_score": 7,
        "issues": [],
    }
    defaults.update(overrides)
    return ReviewOutput(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A. Valid output passes through
# ---------------------------------------------------------------------------


class TestValidOutputPasses:
    """Valid output passes the validator unchanged."""

    @pytest.mark.asyncio
    async def test_valid_approved_output_passes(
        self, agent: ReviewAgent, ctx: RunContext[ReviewDeps]
    ) -> None:
        output = _valid_output()
        result = await agent._validate_output(ctx, output)
        assert result.approved is True
        assert result.feedback == "Good draft with strong prose."

    @pytest.mark.asyncio
    async def test_valid_rejected_with_issues_passes(
        self, agent: ReviewAgent, ctx: RunContext[ReviewDeps]
    ) -> None:
        output = _valid_output(
            approved=False,
            issues=["Pacing is slow in the middle."],
            feedback="Needs work on pacing.",
        )
        result = await agent._validate_output(ctx, output)
        assert result.approved is False
        assert len(result.issues) == 1

    @pytest.mark.asyncio
    async def test_quality_score_boundaries(
        self, agent: ReviewAgent, ctx: RunContext[ReviewDeps]
    ) -> None:
        for score in (1, 5, 10):
            output = _valid_output(quality_score=score)
            result = await agent._validate_output(ctx, output)
            assert result.quality_score == score


# ---------------------------------------------------------------------------
# B. Invariant violations — ModelRetry
# ---------------------------------------------------------------------------


class TestInvariantViolations:
    """Invariant violations raise ModelRetry with helpful messages."""

    @pytest.mark.asyncio
    async def test_quality_score_zero_raises(
        self, agent: ReviewAgent, ctx: RunContext[ReviewDeps]
    ) -> None:
        output = _valid_output(quality_score=0)
        with pytest.raises(ModelRetry, match="between 1 and 10"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_quality_score_eleven_raises(
        self, agent: ReviewAgent, ctx: RunContext[ReviewDeps]
    ) -> None:
        output = _valid_output(quality_score=11)
        with pytest.raises(ModelRetry, match="between 1 and 10"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_empty_feedback_raises(
        self, agent: ReviewAgent, ctx: RunContext[ReviewDeps]
    ) -> None:
        output = _valid_output(feedback="")
        with pytest.raises(ModelRetry, match="non-empty"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_whitespace_only_feedback_raises(
        self, agent: ReviewAgent, ctx: RunContext[ReviewDeps]
    ) -> None:
        output = _valid_output(feedback="   ")
        with pytest.raises(ModelRetry, match="non-empty"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_rejected_without_issues_raises(
        self, agent: ReviewAgent, ctx: RunContext[ReviewDeps]
    ) -> None:
        output = _valid_output(approved=False, issues=[], feedback="Not good.")
        with pytest.raises(ModelRetry, match="at least one issue"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# C. Filter empty strings
# ---------------------------------------------------------------------------


class TestFilterEmptyStrings:
    """Empty strings are filtered from suggestions and issues."""

    @pytest.mark.asyncio
    async def test_filter_empty_suggestions(
        self, agent: ReviewAgent, ctx: RunContext[ReviewDeps]
    ) -> None:
        output = _valid_output(
            suggestions=["Valid suggestion", "", "   ", "Another one"],
        )
        result = await agent._validate_output(ctx, output)
        assert result.suggestions == ["Valid suggestion", "Another one"]

    @pytest.mark.asyncio
    async def test_filter_empty_issues(
        self, agent: ReviewAgent, ctx: RunContext[ReviewDeps]
    ) -> None:
        output = _valid_output(
            approved=False,
            issues=["Real issue", "", "   "],
            feedback="Not good.",
        )
        result = await agent._validate_output(ctx, output)
        assert result.issues == ["Real issue"]


# ---------------------------------------------------------------------------
# D. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_all_suggestions_filtered(
        self, agent: ReviewAgent, ctx: RunContext[ReviewDeps]
    ) -> None:
        """All suggestions empty — passes (empty list is valid)."""
        output = _valid_output(suggestions=["", "   "])
        result = await agent._validate_output(ctx, output)
        assert result.suggestions == []

    @pytest.mark.asyncio
    async def test_rejected_with_only_empty_issues_raises(
        self, agent: ReviewAgent, ctx: RunContext[ReviewDeps]
    ) -> None:
        """Empty issues after filtering = no issues → raises."""
        output = _valid_output(
            approved=False,
            issues=["", "   "],
            feedback="Not good.",
        )
        with pytest.raises(ModelRetry, match="at least one issue"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# E. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_pass(
        self, agent: ReviewAgent, ctx: RunContext[ReviewDeps]
    ) -> None:
        output = _valid_output()
        result1 = await agent._validate_output(ctx, output)
        result2 = await agent._validate_output(ctx, output)
        assert result1.feedback == result2.feedback

    @pytest.mark.asyncio
    async def test_deterministic_retry(
        self, agent: ReviewAgent, ctx: RunContext[ReviewDeps]
    ) -> None:
        output = _valid_output(feedback="")
        for _ in range(3):
            with pytest.raises(ModelRetry, match="non-empty"):
                await agent._validate_output(ctx, output)
