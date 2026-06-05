"""Tests for ReadabilityAgent output validator — ADR-035.

Tests the deterministic invariants enforced by _validate_output:
- overall_assessment must be non-empty
- Filter problematic_sentences with empty content

Test strategy:
- Call _validate_output directly with mocked RunContext
- No real LLM calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.readability_agent import ReadabilityAgent, ReadabilityDeps
from narrare_core.agents.readability_types import ReadabilityAgentOutput

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> ReadabilityAgent:
    return ReadabilityAgent(model=TestModel())


@pytest.fixture()
def ctx() -> RunContext[ReadabilityDeps]:
    return RunContext[ReadabilityDeps](
        deps=ReadabilityDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _valid_output(**overrides: object) -> ReadabilityAgentOutput:
    """Build a valid ReadabilityAgentOutput for testing."""
    defaults: dict[str, object] = {
        "overall_assessment": "The text is generally readable with some long sentences.",
        "problematic_sentences": [
            {
                "content": "This sentence is too long and convoluted.",
                "issues": [{"type": "too_long", "description": "35 words"}],
            }
        ],
    }
    defaults.update(overrides)
    return ReadabilityAgentOutput(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A. Valid output passes through
# ---------------------------------------------------------------------------


class TestValidOutputPasses:
    """Valid output passes the validator unchanged."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(
        self, agent: ReadabilityAgent, ctx: RunContext[ReadabilityDeps]
    ) -> None:
        output = _valid_output()
        result = await agent._validate_output(ctx, output)
        assert "readable" in result.overall_assessment
        assert len(result.problematic_sentences) == 1

    @pytest.mark.asyncio
    async def test_empty_problematic_sentences_passes(
        self, agent: ReadabilityAgent, ctx: RunContext[ReadabilityDeps]
    ) -> None:
        output = _valid_output(problematic_sentences=[])
        result = await agent._validate_output(ctx, output)
        assert result.problematic_sentences == []

    @pytest.mark.asyncio
    async def test_sentence_with_sentence_key_passes(
        self, agent: ReadabilityAgent, ctx: RunContext[ReadabilityDeps]
    ) -> None:
        """The validator checks both 'content' and 'sentence' keys."""
        output = _valid_output(
            problematic_sentences=[
                {"sentence": "A valid sentence.", "issues": []},
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.problematic_sentences) == 1


# ---------------------------------------------------------------------------
# B. Invariant violations — ModelRetry
# ---------------------------------------------------------------------------


class TestInvariantViolations:
    """Invariant violations raise ModelRetry with helpful messages."""

    @pytest.mark.asyncio
    async def test_empty_overall_assessment_raises(
        self, agent: ReadabilityAgent, ctx: RunContext[ReadabilityDeps]
    ) -> None:
        output = _valid_output(overall_assessment="")
        with pytest.raises(ModelRetry, match="non-empty"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_whitespace_only_assessment_raises(
        self, agent: ReadabilityAgent, ctx: RunContext[ReadabilityDeps]
    ) -> None:
        output = _valid_output(overall_assessment="   ")
        with pytest.raises(ModelRetry, match="non-empty"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# C. Filter empty content sentences
# ---------------------------------------------------------------------------


class TestFilterEmptySentences:
    """Problematic sentences with empty content are filtered."""

    @pytest.mark.asyncio
    async def test_filter_empty_content(
        self, agent: ReadabilityAgent, ctx: RunContext[ReadabilityDeps]
    ) -> None:
        output = _valid_output(
            problematic_sentences=[
                {"content": "", "issues": []},
                {"content": "Valid sentence", "issues": []},
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.problematic_sentences) == 1
        assert result.problematic_sentences[0]["content"] == "Valid sentence"

    @pytest.mark.asyncio
    async def test_filter_whitespace_content(
        self, agent: ReadabilityAgent, ctx: RunContext[ReadabilityDeps]
    ) -> None:
        output = _valid_output(
            problematic_sentences=[
                {"content": "   ", "issues": []},
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert result.problematic_sentences == []

    @pytest.mark.asyncio
    async def test_filter_no_content_key(
        self, agent: ReadabilityAgent, ctx: RunContext[ReadabilityDeps]
    ) -> None:
        """Dict with neither 'content' nor 'sentence' key gets filtered."""
        output = _valid_output(
            problematic_sentences=[
                {"issues": [{"type": "too_long"}]},
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert result.problematic_sentences == []

    @pytest.mark.asyncio
    async def test_all_sentences_filtered(
        self, agent: ReadabilityAgent, ctx: RunContext[ReadabilityDeps]
    ) -> None:
        output = _valid_output(
            problematic_sentences=[
                {"content": "", "issues": []},
                {"content": "  ", "issues": []},
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert result.problematic_sentences == []


# ---------------------------------------------------------------------------
# D. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_pass(
        self, agent: ReadabilityAgent, ctx: RunContext[ReadabilityDeps]
    ) -> None:
        output = _valid_output()
        result1 = await agent._validate_output(ctx, output)
        result2 = await agent._validate_output(ctx, output)
        assert result1.overall_assessment == result2.overall_assessment

    @pytest.mark.asyncio
    async def test_deterministic_retry(
        self, agent: ReadabilityAgent, ctx: RunContext[ReadabilityDeps]
    ) -> None:
        output = _valid_output(overall_assessment="")
        for _ in range(3):
            with pytest.raises(ModelRetry, match="non-empty"):
                await agent._validate_output(ctx, output)
