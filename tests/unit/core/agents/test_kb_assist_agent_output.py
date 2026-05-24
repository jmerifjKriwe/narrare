"""Tests for KBAssistAgent._process_output — output structuring.

Split from test_kb_assist_agent.py per RULE-04 (file size limit).
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.kb_assist_agent import KBAssistAgent, KBAssistDeps

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_model() -> TestModel:
    return TestModel()


@pytest.fixture()
def agent(test_model: TestModel) -> KBAssistAgent:
    return KBAssistAgent(model=test_model)


@pytest.fixture()
def run_context(test_model: TestModel) -> RunContext[KBAssistDeps]:
    return RunContext[KBAssistDeps](
        deps=KBAssistDeps(),
        model=test_model,
        usage=RunUsage(),
    )


# ---------------------------------------------------------------------------
# _process_output tests
# ---------------------------------------------------------------------------


class TestProcessOutput:
    """_process_output structures LLM response into KBAssistOutput."""

    @pytest.mark.asyncio
    async def test_returns_question_output(
        self, agent: KBAssistAgent, run_context: RunContext[KBAssistDeps]
    ) -> None:
        result = await agent._process_output(
            run_context,
            mode="question",
            question="What is the character's name?",
            field_key="name",
            reasoning="Name is the core identity field.",
        )
        assert result.mode == "question"
        assert result.question == "What is the character's name?"
        assert result.field_key == "name"
        assert result.reasoning == "Name is the core identity field."

    @pytest.mark.asyncio
    async def test_returns_suggestion_output(
        self, agent: KBAssistAgent, run_context: RunContext[KBAssistDeps]
    ) -> None:
        result = await agent._process_output(
            run_context,
            mode="suggestion",
            suggestion="A tower of pale marble",
            field_key="appearance",
            context_used=["The Dark Woods"],
        )
        assert result.mode == "suggestion"
        assert result.suggestion == "A tower of pale marble"
        assert result.field_key == "appearance"
        assert result.context_used == ["The Dark Woods"]

    @pytest.mark.asyncio
    async def test_returns_draft_output(
        self, agent: KBAssistAgent, run_context: RunContext[KBAssistDeps]
    ) -> None:
        result = await agent._process_output(
            run_context,
            mode="draft",
            draft_entry={"name": "Anna", "role": "protagonist"},
            progress=0.5,
            context_used=["The Tower"],
        )
        assert result.mode == "draft"
        assert result.draft_entry == {"name": "Anna", "role": "protagonist"}
        assert result.progress == 0.5

    @pytest.mark.asyncio
    async def test_returns_complete_output(
        self, agent: KBAssistAgent, run_context: RunContext[KBAssistDeps]
    ) -> None:
        final = {"name": "Anna", "role": "protagonist", "age": 28}
        result = await agent._process_output(
            run_context,
            mode="complete",
            final_entry=final,
            progress=1.0,
        )
        assert result.mode == "complete"
        assert result.final_entry == final
        assert result.progress == 1.0

    @pytest.mark.asyncio
    async def test_partial_output_returns_minimal(
        self, agent: KBAssistAgent, run_context: RunContext[KBAssistDeps]
    ) -> None:
        run_context.partial_output = True
        result = await agent._process_output(
            run_context,
            mode="question",
            question="Ignored during streaming",
            field_key="name",
        )
        assert result.mode == "question"
        assert result.question is None
        assert result.field_key is None
