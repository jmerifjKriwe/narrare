"""Tests for PreferenceAnalysisAgent output validator — ADR-035.

Tests the deterministic invariants enforced by _validate_output:
- Pattern lists stripped, filtered, and deduplicated
- At least one pattern list non-empty when confidence > 0.0
- confidence in [0.0, 1.0]
- summary non-empty when confidence > 0.3

Test strategy:
- Call _validate_output directly with mocked RunContext
- No real LLM calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.preference_analysis_agent import (
    PreferenceAnalysisAgent,
    PreferenceAnalysisDeps,
)
from narrare_core.agents.preference_analysis_types import PreferenceAnalysisOutput

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> PreferenceAnalysisAgent:
    return PreferenceAnalysisAgent(model=TestModel())


@pytest.fixture()
def ctx() -> RunContext[PreferenceAnalysisDeps]:
    return RunContext[PreferenceAnalysisDeps](
        deps=PreferenceAnalysisDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _valid_output(**overrides: object) -> PreferenceAnalysisOutput:
    """Build a valid PreferenceAnalysisOutput for testing."""
    defaults: dict[str, object] = {
        "style_patterns": ["prefers concise sentences"],
        "content_patterns": ["favors dialogue"],
        "avoidance_patterns": ["dislikes cliffhangers"],
        "confidence": 0.8,
        "summary": "User prefers tight prose with dialogue.",
    }
    defaults.update(overrides)
    return PreferenceAnalysisOutput(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A. Valid output passes through
# ---------------------------------------------------------------------------


class TestValidOutputPasses:
    """Valid output passes the validator unchanged (except cleanup)."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        output = _valid_output()
        result = await agent._validate_output(ctx, output)
        assert isinstance(result, PreferenceAnalysisOutput)
        assert "concise" in result.style_patterns[0]

    @pytest.mark.asyncio
    async def test_valid_output_with_zero_confidence_and_empty_patterns(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        """confidence=0.0 with empty patterns is valid."""
        output = PreferenceAnalysisOutput(confidence=0.0)
        result = await agent._validate_output(ctx, output)
        assert result.confidence == 0.0
        assert result.style_patterns == []

    @pytest.mark.asyncio
    async def test_valid_output_at_confidence_boundary_03(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        """confidence=0.3 exactly — summary can be empty (boundary is > 0.3)."""
        output = _valid_output(confidence=0.3, summary="")
        result = await agent._validate_output(ctx, output)
        assert result.confidence == 0.3


# ---------------------------------------------------------------------------
# B. Pattern cleanup — strip, filter, deduplicate
# ---------------------------------------------------------------------------


class TestPatternCleanup:
    """Validator strips, filters, and deduplicates pattern lists."""

    @pytest.mark.asyncio
    async def test_strips_whitespace_from_patterns(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        output = _valid_output(
            style_patterns=["  concise  ", "  dialogue-heavy  "],
            confidence=0.5,
            summary="Summary",
        )
        result = await agent._validate_output(ctx, output)
        assert result.style_patterns == ["concise", "dialogue-heavy"]

    @pytest.mark.asyncio
    async def test_filters_empty_and_whitespace_only_patterns(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        output = _valid_output(
            style_patterns=["concise", "", "  ", "descriptive"],
            confidence=0.5,
            summary="Summary",
        )
        result = await agent._validate_output(ctx, output)
        assert result.style_patterns == ["concise", "descriptive"]

    @pytest.mark.asyncio
    async def test_deduplicates_patterns(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        output = _valid_output(
            style_patterns=["concise", "concise", "descriptive"],
            confidence=0.5,
            summary="Summary",
        )
        result = await agent._validate_output(ctx, output)
        assert result.style_patterns == ["concise", "descriptive"]

    @pytest.mark.asyncio
    async def test_deduplicates_across_all_lists(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        output = _valid_output(
            content_patterns=["dialogue", "dialogue", "action", "action"],
            confidence=0.5,
            summary="Summary",
        )
        result = await agent._validate_output(ctx, output)
        assert result.content_patterns == ["dialogue", "action"]

    @pytest.mark.asyncio
    async def test_preserves_order_after_dedup(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        output = _valid_output(
            avoidance_patterns=["A", "B", "A", "C", "B"],
            confidence=0.5,
            summary="Summary",
        )
        result = await agent._validate_output(ctx, output)
        assert result.avoidance_patterns == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# C. Invariant violations — ModelRetry
# ---------------------------------------------------------------------------


class TestInvariantViolations:
    """Invariant violations raise ModelRetry with helpful messages."""

    @pytest.mark.asyncio
    async def test_no_patterns_with_positive_confidence_raises(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        output = PreferenceAnalysisOutput(
            confidence=0.5,
            style_patterns=[],
            content_patterns=[],
            avoidance_patterns=[],
        )
        with pytest.raises(ModelRetry, match="At least one pattern list"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_summary_missing_when_confidence_above_threshold(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        output = _valid_output(confidence=0.5, summary="")
        with pytest.raises(ModelRetry, match="Summary must be non-empty"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_summary_whitespace_only_when_confidence_above_threshold(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        output = _valid_output(confidence=0.5, summary="   ")
        with pytest.raises(ModelRetry, match="Summary must be non-empty"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_confidence_above_one_raises(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        """Schema normally prevents this, but validator double-checks."""
        output = _valid_output()
        output = output.model_copy(update={"confidence": 1.5})
        with pytest.raises(ModelRetry, match="Confidence must be between"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_confidence_below_zero_raises(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        output = _valid_output()
        output = output.model_copy(update={"confidence": -0.1})
        with pytest.raises(ModelRetry, match="Confidence must be between"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# D. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_all_patterns_whitespace_only_with_positive_confidence(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        """Whitespace-only patterns are filtered → empty lists → triggers ModelRetry."""
        output = PreferenceAnalysisOutput(
            style_patterns=["  ", ""],
            content_patterns=["\t"],
            avoidance_patterns=["\n"],
            confidence=0.5,
        )
        with pytest.raises(ModelRetry, match="At least one pattern list"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_confidence_exactly_zero_allows_empty_patterns(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        output = PreferenceAnalysisOutput(confidence=0.0)
        result = await agent._validate_output(ctx, output)
        assert result.style_patterns == []
        assert result.content_patterns == []
        assert result.avoidance_patterns == []

    @pytest.mark.asyncio
    async def test_confidence_exactly_one(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        output = _valid_output(confidence=1.0)
        result = await agent._validate_output(ctx, output)
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_summary_required_at_just_above_threshold(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        """confidence=0.31 > 0.3, so summary is required."""
        output = _valid_output(confidence=0.31, summary="")
        with pytest.raises(ModelRetry, match="Summary must be non-empty"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# E. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_pass(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        output = _valid_output()
        result1 = await agent._validate_output(ctx, output)
        result2 = await agent._validate_output(ctx, output)
        assert result1.style_patterns == result2.style_patterns
        assert result1.confidence == result2.confidence

    @pytest.mark.asyncio
    async def test_deterministic_retry(
        self, agent: PreferenceAnalysisAgent, ctx: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        output = PreferenceAnalysisOutput(confidence=0.5)
        for _ in range(3):
            with pytest.raises(ModelRetry, match="At least one pattern list"):
                await agent._validate_output(ctx, output)
