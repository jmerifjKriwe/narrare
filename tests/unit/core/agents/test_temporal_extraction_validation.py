"""Tests for TemporalExtractionAgent output validator — ADR-035.

Tests the deterministic invariants enforced by _validate_output:
- expression must be non-empty for each extraction
- Filter extractions with empty expression
- Confidence bounds enforcement (0.0-1.0)

Test strategy:
- Call _validate_output directly with mocked RunContext
- No real LLM calls (RULE-01b)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.temporal_extraction_agent import (
    TemporalExtractionAgent,
    TemporalExtractionDeps,
)
from narrare_core.agents.temporal_extraction_types import (
    ExtractedTemporalExpression,
    TemporalExtractionOutput,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> TemporalExtractionAgent:
    return TemporalExtractionAgent(model=TestModel())


@pytest.fixture()
def ctx() -> RunContext[TemporalExtractionDeps]:
    return RunContext[TemporalExtractionDeps](
        deps=TemporalExtractionDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _make_expression(**overrides: object) -> ExtractedTemporalExpression:
    """Build a valid ExtractedTemporalExpression for testing."""
    defaults: dict[str, object] = {
        "expression": "three days later",
        "event_name": "Arrival at the castle",
        "confidence": 0.85,
    }
    defaults.update(overrides)
    return ExtractedTemporalExpression(**defaults)  # type: ignore[arg-type]


def _valid_output(**overrides: object) -> TemporalExtractionOutput:
    """Build a valid TemporalExtractionOutput for testing."""
    defaults: dict[str, object] = {
        "extracted": [_make_expression()],
        "extraction_notes": "Found one temporal expression.",
    }
    defaults.update(overrides)
    return TemporalExtractionOutput(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A. Valid output passes through
# ---------------------------------------------------------------------------


class TestValidOutputPasses:
    """Valid output passes the validator unchanged."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(
        self, agent: TemporalExtractionAgent, ctx: RunContext[TemporalExtractionDeps]
    ) -> None:
        output = _valid_output()
        result = await agent._validate_output(ctx, output)
        assert len(result.extracted) == 1
        assert result.extracted[0].expression == "three days later"

    @pytest.mark.asyncio
    async def test_empty_extractions_passes(
        self, agent: TemporalExtractionAgent, ctx: RunContext[TemporalExtractionDeps]
    ) -> None:
        output = _valid_output(extracted=[])
        result = await agent._validate_output(ctx, output)
        assert result.extracted == []


# ---------------------------------------------------------------------------
# B. Filter empty expressions
# ---------------------------------------------------------------------------


class TestFilterEmptyExpressions:
    """Extractions with empty expressions are silently filtered."""

    @pytest.mark.asyncio
    async def test_filter_empty_expression(
        self, agent: TemporalExtractionAgent, ctx: RunContext[TemporalExtractionDeps]
    ) -> None:
        output = _valid_output(
            extracted=[
                _make_expression(expression=""),
                _make_expression(expression="three days later"),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.extracted) == 1
        assert result.extracted[0].expression == "three days later"

    @pytest.mark.asyncio
    async def test_filter_whitespace_expression(
        self, agent: TemporalExtractionAgent, ctx: RunContext[TemporalExtractionDeps]
    ) -> None:
        output = _valid_output(
            extracted=[
                _make_expression(expression="   "),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert result.extracted == []

    @pytest.mark.asyncio
    async def test_all_expressions_filtered(
        self, agent: TemporalExtractionAgent, ctx: RunContext[TemporalExtractionDeps]
    ) -> None:
        output = _valid_output(
            extracted=[
                _make_expression(expression=""),
                _make_expression(expression="  "),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert result.extracted == []


# ---------------------------------------------------------------------------
# C. Confidence bounds
# ---------------------------------------------------------------------------


class TestConfidenceBounds:
    """Confidence must be between 0.0 and 1.0."""

    @pytest.mark.asyncio
    async def test_confidence_above_one_raises(
        self, agent: TemporalExtractionAgent, ctx: RunContext[TemporalExtractionDeps]
    ) -> None:
        output = _valid_output(extracted=[_make_expression(confidence=1.5)])
        with pytest.raises(ModelRetry, match=r"between 0.0 and 1.0"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_confidence_below_zero_raises(
        self, agent: TemporalExtractionAgent, ctx: RunContext[TemporalExtractionDeps]
    ) -> None:
        output = _valid_output(extracted=[_make_expression(confidence=-0.1)])
        with pytest.raises(ModelRetry, match=r"between 0.0 and 1.0"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_confidence_at_boundaries_passes(
        self, agent: TemporalExtractionAgent, ctx: RunContext[TemporalExtractionDeps]
    ) -> None:
        for conf in (0.0, 1.0):
            output = _valid_output(extracted=[_make_expression(confidence=conf)])
            result = await agent._validate_output(ctx, output)
            assert result.extracted[0].confidence == conf


# ---------------------------------------------------------------------------
# D. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_pass(
        self, agent: TemporalExtractionAgent, ctx: RunContext[TemporalExtractionDeps]
    ) -> None:
        output = _valid_output()
        result1 = await agent._validate_output(ctx, output)
        result2 = await agent._validate_output(ctx, output)
        assert len(result1.extracted) == len(result2.extracted)

    @pytest.mark.asyncio
    async def test_deterministic_retry(
        self, agent: TemporalExtractionAgent, ctx: RunContext[TemporalExtractionDeps]
    ) -> None:
        output = _valid_output(extracted=[_make_expression(confidence=2.0)])
        for _ in range(3):
            with pytest.raises(ModelRetry, match=r"between 0.0 and 1.0"):
                await agent._validate_output(ctx, output)
