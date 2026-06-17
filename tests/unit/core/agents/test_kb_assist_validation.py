"""Tests for KBAssistAgent output validator — ADR-035.

Tests the deterministic invariants enforced by _validate_output:
- Mode-dependent field presence:
  - "question" mode → question non-empty, field_key non-empty
  - "suggestion" mode → suggestion non-empty, field_key non-empty
  - "draft" mode → draft_entry must be non-empty dict
  - "complete" mode → final_entry must be non-empty dict

Test strategy:
- Call _validate_output directly with mocked RunContext
- No real LLM calls (RULE-01b)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.kb_assist_agent import KBAssistAgent, KBAssistDeps
from narrare_core.agents.kb_assist_types import KBAssistOutput

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> KBAssistAgent:
    return KBAssistAgent(model=TestModel())


@pytest.fixture()
def ctx() -> RunContext[KBAssistDeps]:
    return RunContext[KBAssistDeps](
        deps=KBAssistDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


# ---------------------------------------------------------------------------
# A. Valid output passes through (all 4 modes)
# ---------------------------------------------------------------------------


class TestValidOutputPasses:
    """Valid output passes the validator unchanged for each mode."""

    @pytest.mark.asyncio
    async def test_valid_question_mode(
        self, agent: KBAssistAgent, ctx: RunContext[KBAssistDeps]
    ) -> None:
        output = KBAssistOutput(
            mode="question",
            question="What is the character's motivation?",
            field_key="motivation",
        )
        result = await agent._validate_output(ctx, output)
        assert result.mode == "question"

    @pytest.mark.asyncio
    async def test_valid_suggestion_mode(
        self, agent: KBAssistAgent, ctx: RunContext[KBAssistDeps]
    ) -> None:
        output = KBAssistOutput(
            mode="suggestion",
            suggestion="Driven by revenge after losing family.",
            field_key="motivation",
        )
        result = await agent._validate_output(ctx, output)
        assert result.mode == "suggestion"

    @pytest.mark.asyncio
    async def test_valid_draft_mode(
        self, agent: KBAssistAgent, ctx: RunContext[KBAssistDeps]
    ) -> None:
        output = KBAssistOutput(
            mode="draft",
            draft_entry={"name": "Anna", "age": 28},
        )
        result = await agent._validate_output(ctx, output)
        assert result.mode == "draft"

    @pytest.mark.asyncio
    async def test_valid_complete_mode(
        self, agent: KBAssistAgent, ctx: RunContext[KBAssistDeps]
    ) -> None:
        output = KBAssistOutput(
            mode="complete",
            final_entry={"name": "Anna", "age": 28, "backstory": "..."},
        )
        result = await agent._validate_output(ctx, output)
        assert result.mode == "complete"


# ---------------------------------------------------------------------------
# B. Question mode violations
# ---------------------------------------------------------------------------


class TestQuestionModeViolations:
    @pytest.mark.asyncio
    async def test_empty_question_raises(
        self, agent: KBAssistAgent, ctx: RunContext[KBAssistDeps]
    ) -> None:
        output = KBAssistOutput(
            mode="question",
            question="",
            field_key="motivation",
        )
        with pytest.raises(ModelRetry, match="non-empty 'question'"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_whitespace_question_raises(
        self, agent: KBAssistAgent, ctx: RunContext[KBAssistDeps]
    ) -> None:
        output = KBAssistOutput(
            mode="question",
            question="   ",
            field_key="motivation",
        )
        with pytest.raises(ModelRetry, match="non-empty 'question'"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_empty_field_key_raises(
        self, agent: KBAssistAgent, ctx: RunContext[KBAssistDeps]
    ) -> None:
        output = KBAssistOutput(
            mode="question",
            question="What is the motivation?",
            field_key="",
        )
        with pytest.raises(ModelRetry, match="non-empty 'field_key'"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# C. Suggestion mode violations
# ---------------------------------------------------------------------------


class TestSuggestionModeViolations:
    @pytest.mark.asyncio
    async def test_empty_suggestion_raises(
        self, agent: KBAssistAgent, ctx: RunContext[KBAssistDeps]
    ) -> None:
        output = KBAssistOutput(
            mode="suggestion",
            suggestion="",
            field_key="motivation",
        )
        with pytest.raises(ModelRetry, match="non-empty 'suggestion'"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_empty_field_key_raises(
        self, agent: KBAssistAgent, ctx: RunContext[KBAssistDeps]
    ) -> None:
        output = KBAssistOutput(
            mode="suggestion",
            suggestion="Revenge-driven",
            field_key="",
        )
        with pytest.raises(ModelRetry, match="non-empty 'field_key'"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# D. Draft mode violations
# ---------------------------------------------------------------------------


class TestDraftModeViolations:
    @pytest.mark.asyncio
    async def test_empty_draft_entry_raises(
        self, agent: KBAssistAgent, ctx: RunContext[KBAssistDeps]
    ) -> None:
        output = KBAssistOutput(
            mode="draft",
            draft_entry={},
        )
        with pytest.raises(ModelRetry, match="non-empty 'draft_entry'"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_none_draft_entry_raises(
        self, agent: KBAssistAgent, ctx: RunContext[KBAssistDeps]
    ) -> None:
        output = KBAssistOutput(
            mode="draft",
            draft_entry=None,
        )
        with pytest.raises(ModelRetry, match="non-empty 'draft_entry'"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# E. Complete mode violations
# ---------------------------------------------------------------------------


class TestCompleteModeViolations:
    @pytest.mark.asyncio
    async def test_empty_final_entry_raises(
        self, agent: KBAssistAgent, ctx: RunContext[KBAssistDeps]
    ) -> None:
        output = KBAssistOutput(
            mode="complete",
            final_entry={},
        )
        with pytest.raises(ModelRetry, match="non-empty 'final_entry'"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_none_final_entry_raises(
        self, agent: KBAssistAgent, ctx: RunContext[KBAssistDeps]
    ) -> None:
        output = KBAssistOutput(
            mode="complete",
            final_entry=None,
        )
        with pytest.raises(ModelRetry, match="non-empty 'final_entry'"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# F. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_pass(
        self, agent: KBAssistAgent, ctx: RunContext[KBAssistDeps]
    ) -> None:
        output = KBAssistOutput(
            mode="question",
            question="What is the motivation?",
            field_key="motivation",
        )
        result1 = await agent._validate_output(ctx, output)
        result2 = await agent._validate_output(ctx, output)
        assert result1.question == result2.question

    @pytest.mark.asyncio
    async def test_deterministic_retry(
        self, agent: KBAssistAgent, ctx: RunContext[KBAssistDeps]
    ) -> None:
        output = KBAssistOutput(
            mode="question",
            question="",
            field_key="motivation",
        )
        for _ in range(3):
            with pytest.raises(ModelRetry, match="non-empty 'question'"):
                await agent._validate_output(ctx, output)
