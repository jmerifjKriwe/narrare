"""Tests for ChapterSummaryAgent output validator — ADR-035.

Tests the deterministic invariants enforced by _validate_output:
- summary must be non-empty
- key_points should have non-empty strings (filter empty)
- At least one key_point when summary is non-empty

Test strategy:
- Call _validate_output directly with mocked RunContext
- No real LLM calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.summary_agent import ChapterSummaryAgent, SummaryDeps
from narrare_core.agents.summary_types import SummaryOutput

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> ChapterSummaryAgent:
    return ChapterSummaryAgent(model=TestModel())


@pytest.fixture()
def ctx() -> RunContext[SummaryDeps]:
    return RunContext[SummaryDeps](
        deps=SummaryDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _valid_output(**overrides: object) -> SummaryOutput:
    """Build a valid SummaryOutput for testing."""
    defaults: dict[str, object] = {
        "summary": "The hero arrives at the castle and meets the queen.",
        "key_points": ["Arrival at castle", "Meeting with queen"],
    }
    defaults.update(overrides)
    return SummaryOutput(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A. Valid output passes through
# ---------------------------------------------------------------------------


class TestValidOutputPasses:
    """Valid output passes the validator unchanged."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(
        self, agent: ChapterSummaryAgent, ctx: RunContext[SummaryDeps]
    ) -> None:
        output = _valid_output()
        result = await agent._validate_output(ctx, output)
        assert "hero" in result.summary
        assert len(result.key_points) == 2

    @pytest.mark.asyncio
    async def test_valid_with_single_key_point(
        self, agent: ChapterSummaryAgent, ctx: RunContext[SummaryDeps]
    ) -> None:
        output = _valid_output(key_points=["Arrival"])
        result = await agent._validate_output(ctx, output)
        assert result.key_points == ["Arrival"]


# ---------------------------------------------------------------------------
# B. Invariant violations — ModelRetry
# ---------------------------------------------------------------------------


class TestInvariantViolations:
    """Invariant violations raise ModelRetry with helpful messages."""

    @pytest.mark.asyncio
    async def test_empty_summary_raises(
        self, agent: ChapterSummaryAgent, ctx: RunContext[SummaryDeps]
    ) -> None:
        output = _valid_output(summary="")
        with pytest.raises(ModelRetry, match="non-empty"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_whitespace_only_summary_raises(
        self, agent: ChapterSummaryAgent, ctx: RunContext[SummaryDeps]
    ) -> None:
        output = _valid_output(summary="   ")
        with pytest.raises(ModelRetry, match="non-empty"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_no_key_points_raises(
        self, agent: ChapterSummaryAgent, ctx: RunContext[SummaryDeps]
    ) -> None:
        output = _valid_output(key_points=[])
        with pytest.raises(ModelRetry, match="At least one key_point"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# C. Filter empty key points
# ---------------------------------------------------------------------------


class TestFilterEmptyKeyPoints:
    """Empty key points are silently filtered."""

    @pytest.mark.asyncio
    async def test_filter_empty_key_points(
        self, agent: ChapterSummaryAgent, ctx: RunContext[SummaryDeps]
    ) -> None:
        output = _valid_output(key_points=["Valid", "", "   ", "Also valid"])
        result = await agent._validate_output(ctx, output)
        assert result.key_points == ["Valid", "Also valid"]

    @pytest.mark.asyncio
    async def test_all_key_points_empty_raises(
        self, agent: ChapterSummaryAgent, ctx: RunContext[SummaryDeps]
    ) -> None:
        output = _valid_output(key_points=["", "   "])
        with pytest.raises(ModelRetry, match="At least one key_point"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# D. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_pass(
        self, agent: ChapterSummaryAgent, ctx: RunContext[SummaryDeps]
    ) -> None:
        output = _valid_output()
        result1 = await agent._validate_output(ctx, output)
        result2 = await agent._validate_output(ctx, output)
        assert result1.summary == result2.summary
        assert result1.key_points == result2.key_points

    @pytest.mark.asyncio
    async def test_deterministic_retry(
        self, agent: ChapterSummaryAgent, ctx: RunContext[SummaryDeps]
    ) -> None:
        output = _valid_output(summary="")
        for _ in range(3):
            with pytest.raises(ModelRetry, match="non-empty"):
                await agent._validate_output(ctx, output)
