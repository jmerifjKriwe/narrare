"""Tests for DraftAgent output validator — ADR-035.

Tests the deterministic invariants enforced by _validate_output:
- text must be non-empty
- word_count should approximately match len(text.split()) (±2 tolerance)
- scene_breaks positions must be valid (>= 0, <= len(text))

Test strategy:
- Call _validate_output directly with mocked RunContext
- No real LLM calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.draft_types import DraftDeps, DraftOutput
from narrare_core.agents.draft_validators import validate_draft_output

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ctx() -> RunContext[DraftDeps]:
    return RunContext[DraftDeps](
        deps=DraftDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _valid_output(**overrides: object) -> DraftOutput:
    """Build a valid DraftOutput for testing."""
    defaults: dict[str, object] = {
        "text": "The wind howled through the narrow streets.",
        "word_count": 7,
        "scene_breaks": [],
    }
    defaults.update(overrides)
    return DraftOutput(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A. Valid output passes through
# ---------------------------------------------------------------------------


class TestValidOutputPasses:
    """Valid output passes the validator unchanged."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(self, ctx: RunContext[DraftDeps]) -> None:
        output = _valid_output()
        result = await validate_draft_output(ctx, output)
        assert result.text == "The wind howled through the narrow streets."

    @pytest.mark.asyncio
    async def test_valid_with_scene_breaks(self, ctx: RunContext[DraftDeps]) -> None:
        text = "Part one. *** Part two."
        output = _valid_output(text=text, scene_breaks=[10], word_count=5)
        result = await validate_draft_output(ctx, output)
        assert 10 in result.scene_breaks

    @pytest.mark.asyncio
    async def test_scene_break_at_end_of_text(self, ctx: RunContext[DraftDeps]) -> None:
        text = "Hello world"
        output = _valid_output(text=text, scene_breaks=[11], word_count=2)
        result = await validate_draft_output(ctx, output)
        assert 11 in result.scene_breaks


# ---------------------------------------------------------------------------
# B. Invariant violations — ModelRetry
# ---------------------------------------------------------------------------


class TestInvariantViolations:
    """Invariant violations raise ModelRetry with helpful messages."""

    @pytest.mark.asyncio
    async def test_empty_text_raises(self, ctx: RunContext[DraftDeps]) -> None:
        output = _valid_output(text="")
        with pytest.raises(ModelRetry, match="non-empty"):
            await validate_draft_output(ctx, output)

    @pytest.mark.asyncio
    async def test_whitespace_only_text_raises(self, ctx: RunContext[DraftDeps]) -> None:
        output = _valid_output(text="   \n\t  ")
        with pytest.raises(ModelRetry, match="non-empty"):
            await validate_draft_output(ctx, output)

    @pytest.mark.asyncio
    async def test_negative_scene_break_raises(self, ctx: RunContext[DraftDeps]) -> None:
        output = _valid_output(scene_breaks=[-1])
        with pytest.raises(ModelRetry, match="negative"):
            await validate_draft_output(ctx, output)

    @pytest.mark.asyncio
    async def test_scene_break_exceeds_text_length_raises(self, ctx: RunContext[DraftDeps]) -> None:
        text = "Hello"
        output = _valid_output(text=text, scene_breaks=[100])
        with pytest.raises(ModelRetry, match="exceeds text length"):
            await validate_draft_output(ctx, output)


# ---------------------------------------------------------------------------
# C. Word count correction
# ---------------------------------------------------------------------------


class TestWordCountCorrection:
    """Word count is corrected when mismatch exceeds tolerance."""

    @pytest.mark.asyncio
    async def test_word_count_corrected_on_large_mismatch(self, ctx: RunContext[DraftDeps]) -> None:
        text = "One two three four five"
        output = _valid_output(text=text, word_count=100)
        result = await validate_draft_output(ctx, output)
        assert result.word_count == 5  # corrected

    @pytest.mark.asyncio
    async def test_word_count_within_tolerance_passes(self, ctx: RunContext[DraftDeps]) -> None:
        text = "One two three four five"
        output = _valid_output(text=text, word_count=6)  # actual=5, diff=1
        result = await validate_draft_output(ctx, output)
        assert result.word_count == 6  # within ±2, kept

    @pytest.mark.asyncio
    async def test_word_count_zero_not_corrected(self, ctx: RunContext[DraftDeps]) -> None:
        text = "One two three"
        output = _valid_output(text=text, word_count=0)
        result = await validate_draft_output(ctx, output)
        assert result.word_count == 0  # zero means "not computed", left alone


# ---------------------------------------------------------------------------
# D. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_scene_break_at_position_zero(self, ctx: RunContext[DraftDeps]) -> None:
        output = _valid_output(scene_breaks=[0])
        result = await validate_draft_output(ctx, output)
        assert 0 in result.scene_breaks

    @pytest.mark.asyncio
    async def test_multiple_scene_breaks_one_invalid(self, ctx: RunContext[DraftDeps]) -> None:
        text = "Hello"
        output = _valid_output(text=text, scene_breaks=[0, 100])
        with pytest.raises(ModelRetry, match="exceeds text length"):
            await validate_draft_output(ctx, output)


# ---------------------------------------------------------------------------
# E. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_pass(self, ctx: RunContext[DraftDeps]) -> None:
        output = _valid_output()
        result1 = await validate_draft_output(ctx, output)
        result2 = await validate_draft_output(ctx, output)
        assert result1.text == result2.text

    @pytest.mark.asyncio
    async def test_deterministic_retry(self, ctx: RunContext[DraftDeps]) -> None:
        output = _valid_output(text="")
        for _ in range(3):
            with pytest.raises(ModelRetry, match="non-empty"):
                await validate_draft_output(ctx, output)
