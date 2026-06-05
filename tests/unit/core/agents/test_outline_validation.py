"""Tests for OutlineAgent output validator — ADR-035.

Tests the deterministic invariants enforced by _validate_output:
- At least one scene
- chapter_title must be non-empty
- Filter empty scene strings

Test strategy:
- Call _validate_output directly with mocked RunContext
- No real LLM calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.outline_agent import OutlineAgent, OutlineDeps
from narrare_core.agents.outline_types import OutlineOutput

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> OutlineAgent:
    return OutlineAgent(model=TestModel())


@pytest.fixture()
def ctx() -> RunContext[OutlineDeps]:
    return RunContext[OutlineDeps](
        deps=OutlineDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _valid_output(**overrides: object) -> OutlineOutput:
    """Build a valid OutlineOutput for testing."""
    defaults: dict[str, object] = {
        "chapter_title": "Chapter 1: The Beginning",
        "scenes": ["Opening in the village", "The stranger arrives"],
        "outline_text": "Opening in the village\n\nThe stranger arrives",
    }
    defaults.update(overrides)
    return OutlineOutput(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A. Valid output passes through
# ---------------------------------------------------------------------------


class TestValidOutputPasses:
    """Valid output passes the validator unchanged."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(
        self, agent: OutlineAgent, ctx: RunContext[OutlineDeps]
    ) -> None:
        output = _valid_output()
        result = await agent._validate_output(ctx, output)
        assert result.chapter_title == "Chapter 1: The Beginning"
        assert len(result.scenes) == 2

    @pytest.mark.asyncio
    async def test_valid_single_scene(
        self, agent: OutlineAgent, ctx: RunContext[OutlineDeps]
    ) -> None:
        output = _valid_output(scenes=["Just one scene"])
        result = await agent._validate_output(ctx, output)
        assert result.scenes == ["Just one scene"]


# ---------------------------------------------------------------------------
# B. Invariant violations — ModelRetry
# ---------------------------------------------------------------------------


class TestInvariantViolations:
    """Invariant violations raise ModelRetry with helpful messages."""

    @pytest.mark.asyncio
    async def test_empty_chapter_title_raises(
        self, agent: OutlineAgent, ctx: RunContext[OutlineDeps]
    ) -> None:
        output = _valid_output(chapter_title="")
        with pytest.raises(ModelRetry, match="non-empty"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_whitespace_chapter_title_raises(
        self, agent: OutlineAgent, ctx: RunContext[OutlineDeps]
    ) -> None:
        output = _valid_output(chapter_title="   ")
        with pytest.raises(ModelRetry, match="non-empty"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_no_scenes_raises(
        self, agent: OutlineAgent, ctx: RunContext[OutlineDeps]
    ) -> None:
        output = _valid_output(scenes=[])
        with pytest.raises(ModelRetry, match="At least one scene"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# C. Filter empty scenes
# ---------------------------------------------------------------------------


class TestFilterEmptyScenes:
    """Empty scene strings are silently filtered."""

    @pytest.mark.asyncio
    async def test_filter_empty_scenes(
        self, agent: OutlineAgent, ctx: RunContext[OutlineDeps]
    ) -> None:
        output = _valid_output(scenes=["Valid scene", "", "   ", "Another"])
        result = await agent._validate_output(ctx, output)
        assert result.scenes == ["Valid scene", "Another"]

    @pytest.mark.asyncio
    async def test_all_scenes_empty_raises(
        self, agent: OutlineAgent, ctx: RunContext[OutlineDeps]
    ) -> None:
        output = _valid_output(scenes=["", "   "])
        with pytest.raises(ModelRetry, match="At least one scene"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# D. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_pass(
        self, agent: OutlineAgent, ctx: RunContext[OutlineDeps]
    ) -> None:
        output = _valid_output()
        result1 = await agent._validate_output(ctx, output)
        result2 = await agent._validate_output(ctx, output)
        assert result1.chapter_title == result2.chapter_title
        assert result1.scenes == result2.scenes

    @pytest.mark.asyncio
    async def test_deterministic_retry(
        self, agent: OutlineAgent, ctx: RunContext[OutlineDeps]
    ) -> None:
        output = _valid_output(chapter_title="")
        for _ in range(3):
            with pytest.raises(ModelRetry, match="non-empty"):
                await agent._validate_output(ctx, output)
