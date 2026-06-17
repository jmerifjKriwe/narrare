"""Tests for KBImproveAgent output validator — ADR-035.

Tests the deterministic invariants enforced by _validate_output:
- target field must be non-empty for each suggestion
- description must be non-empty for each suggestion
- Filter suggestions with empty target or description
- completeness_score clamped to [0.0, 1.0]

Test strategy:
- Call _validate_output directly with mocked RunContext
- No real LLM calls (RULE-01b)
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.kb_improve_agent import KBImproveAgent
from narrare_core.agents.kb_improve_types import (
    ImprovementSuggestion,
    KBImproveDeps,
    KBImproveOutput,
    SuggestionType,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> KBImproveAgent:
    return KBImproveAgent(model=TestModel())


@pytest.fixture()
def ctx() -> RunContext[KBImproveDeps]:
    return RunContext[KBImproveDeps](
        deps=KBImproveDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _make_suggestion(**overrides: object) -> ImprovementSuggestion:
    """Build a valid ImprovementSuggestion for testing."""
    defaults: dict[str, object] = {
        "type": SuggestionType.EXPAND,
        "target": "backstory",
        "description": "The backstory field is sparse.",
        "confidence": 0.8,
    }
    defaults.update(overrides)
    return ImprovementSuggestion(**defaults)  # type: ignore[arg-type]


def _valid_output(**overrides: object) -> KBImproveOutput:
    """Build a valid KBImproveOutput for testing."""
    defaults: dict[str, object] = {
        "suggestions": [_make_suggestion()],
        "overall_assessment": "Entry needs expansion.",
        "completeness_score": 0.4,
    }
    defaults.update(overrides)
    return KBImproveOutput(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A. Valid output passes through
# ---------------------------------------------------------------------------


class TestValidOutputPasses:
    """Valid output passes the validator unchanged."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(
        self, agent: KBImproveAgent, ctx: RunContext[KBImproveDeps]
    ) -> None:
        output = _valid_output()
        result = await agent._validate_output(ctx, output)
        assert len(result.suggestions) == 1
        assert result.completeness_score == 0.4

    @pytest.mark.asyncio
    async def test_empty_suggestions_passes(
        self, agent: KBImproveAgent, ctx: RunContext[KBImproveDeps]
    ) -> None:
        output = _valid_output(suggestions=[])
        result = await agent._validate_output(ctx, output)
        assert result.suggestions == []


# ---------------------------------------------------------------------------
# B. Filter invalid suggestions
# ---------------------------------------------------------------------------


class TestFilterInvalidSuggestions:
    """Suggestions with empty target or description are filtered."""

    @pytest.mark.asyncio
    async def test_filter_empty_target(
        self, agent: KBImproveAgent, ctx: RunContext[KBImproveDeps]
    ) -> None:
        output = _valid_output(
            suggestions=[
                _make_suggestion(target=""),
                _make_suggestion(target="valid"),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.suggestions) == 1
        assert result.suggestions[0].target == "valid"

    @pytest.mark.asyncio
    async def test_filter_empty_description(
        self, agent: KBImproveAgent, ctx: RunContext[KBImproveDeps]
    ) -> None:
        output = _valid_output(
            suggestions=[
                _make_suggestion(description=""),
                _make_suggestion(description="Valid desc"),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.suggestions) == 1
        assert result.suggestions[0].description == "Valid desc"

    @pytest.mark.asyncio
    async def test_all_suggestions_filtered(
        self, agent: KBImproveAgent, ctx: RunContext[KBImproveDeps]
    ) -> None:
        output = _valid_output(
            suggestions=[
                _make_suggestion(target=""),
                _make_suggestion(description=""),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert result.suggestions == []


# ---------------------------------------------------------------------------
# C. Completeness score clamping
# ---------------------------------------------------------------------------


class TestCompletenessScoreClamping:
    """completeness_score is clamped to [0.0, 1.0]."""

    @pytest.mark.asyncio
    async def test_clamp_above_one(
        self, agent: KBImproveAgent, ctx: RunContext[KBImproveDeps]
    ) -> None:
        output = _valid_output()
        output = output.model_copy(update={"completeness_score": 1.5})
        result = await agent._validate_output(ctx, output)
        assert result.completeness_score == 1.0

    @pytest.mark.asyncio
    async def test_clamp_below_zero(
        self, agent: KBImproveAgent, ctx: RunContext[KBImproveDeps]
    ) -> None:
        output = _valid_output()
        output = output.model_copy(update={"completeness_score": -0.5})
        result = await agent._validate_output(ctx, output)
        assert result.completeness_score == 0.0

    @pytest.mark.asyncio
    async def test_valid_score_unchanged(
        self, agent: KBImproveAgent, ctx: RunContext[KBImproveDeps]
    ) -> None:
        output = _valid_output(completeness_score=0.7)
        result = await agent._validate_output(ctx, output)
        assert result.completeness_score == 0.7


# ---------------------------------------------------------------------------
# D. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_pass(
        self, agent: KBImproveAgent, ctx: RunContext[KBImproveDeps]
    ) -> None:
        output = _valid_output()
        result1 = await agent._validate_output(ctx, output)
        result2 = await agent._validate_output(ctx, output)
        assert len(result1.suggestions) == len(result2.suggestions)

    @pytest.mark.asyncio
    async def test_deterministic_clamp(
        self, agent: KBImproveAgent, ctx: RunContext[KBImproveDeps]
    ) -> None:
        output = _valid_output()
        output = output.model_copy(update={"completeness_score": 2.0})
        result1 = await agent._validate_output(ctx, output)
        result2 = await agent._validate_output(ctx, output)
        assert result1.completeness_score == result2.completeness_score == 1.0
