"""Tests for InlineSuggestAgent — instantiation, deps, output, edge cases.

Test strategy:
- TestModel for deterministic agent tests
- FunctionModel for specific output tests
- No real LLM calls (RULE-01)

See test_summary_agent.py for the pattern reference.
"""

from __future__ import annotations

import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from narrare_core.agents.inline_suggest_agent import InlineSuggestAgent
from narrare_core.agents.inline_suggest_types import InlineSuggestDeps

# ---------------------------------------------------------------------------
# A. InlineSuggestDeps
# ---------------------------------------------------------------------------


class TestInlineSuggestDeps:
    """InlineSuggestDeps creates correctly with required and optional fields."""

    def test_deps_fields_present(self) -> None:
        """All expected fields exist on InlineSuggestDeps."""
        deps = InlineSuggestDeps(text_before="Hello world")
        assert hasattr(deps, "text_before")
        assert hasattr(deps, "text_after")
        assert hasattr(deps, "chapter_context")
        assert hasattr(deps, "user_preferences")

    def test_deps_required_field_text_before(self) -> None:
        """text_before is required — constructing without it raises TypeError."""
        with pytest.raises(TypeError):
            InlineSuggestDeps()  # type: ignore[call-arg]

    def test_deps_optional_fields_default_none(self) -> None:
        """Optional fields (text_after, chapter_context, user_preferences) default to None."""
        deps = InlineSuggestDeps(text_before="Some text")
        assert deps.text_after is None
        assert deps.chapter_context is None
        assert deps.user_preferences is None

    def test_deps_with_all_fields(self) -> None:
        """All fields can be set at construction."""
        deps = InlineSuggestDeps(
            text_before="The hero walked into the forest,",
            text_after="He looked back.",
            chapter_context="Chapter 3, POV: First person",
            user_preferences="Prefers short, punchy sentences.",
        )
        assert deps.text_before == "The hero walked into the forest,"
        assert deps.text_after == "He looked back."
        assert deps.chapter_context == "Chapter 3, POV: First person"
        assert deps.user_preferences == "Prefers short, punchy sentences."


# ---------------------------------------------------------------------------
# B. InlineSuggestAgent — Instantiation
# ---------------------------------------------------------------------------


class TestInlineSuggestAgentInstantiation:
    """InlineSuggestAgent instantiates correctly with TestModel."""

    def test_agent_creates_successfully(self) -> None:
        """Agent can be instantiated with TestModel."""
        agent = InlineSuggestAgent(model=TestModel())
        assert isinstance(agent, InlineSuggestAgent)

    def test_agent_system_prompt_key(self) -> None:
        """SYSTEM_PROMPT_KEY is set to 'inline_suggest'."""
        assert InlineSuggestAgent.SYSTEM_PROMPT_KEY == "inline_suggest"

    def test_agent_with_system_prompt(self) -> None:
        """Agent can receive a system_prompt (from PromptComposer)."""
        agent = InlineSuggestAgent(
            model=TestModel(),
            system_prompt="You are a text completion assistant.",
        )
        assert isinstance(agent, InlineSuggestAgent)


# ---------------------------------------------------------------------------
# C. InlineSuggestAgent — Execution
# ---------------------------------------------------------------------------


class TestInlineSuggestAgentExecution:
    """InlineSuggestAgent runs and returns expected output."""

    @pytest.mark.asyncio
    async def test_agent_returns_string_output(self) -> None:
        """Agent output is a plain string."""
        agent = InlineSuggestAgent(model=TestModel())
        deps = InlineSuggestDeps(text_before="The dragon")
        result = await agent.run(prompt="Continue", deps=deps)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_agent_uses_correct_deps(self) -> None:
        """Agent accepts InlineSuggestDeps with all fields populated."""
        agent = InlineSuggestAgent(model=TestModel())
        deps = InlineSuggestDeps(
            text_before="She opened the door and",
            text_after="The room was dark.",
            chapter_context="Chapter 1, POV: Third person",
            user_preferences="No purple prose.",
        )
        result = await agent.run(prompt="Continue", deps=deps)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_agent_with_function_model(self) -> None:
        """FunctionModel returns specific text, agent returns it unchanged."""
        expected = "his footsteps echoing in the silence."
        agent = InlineSuggestAgent(
            model=FunctionModel(
                lambda messages, info: ModelResponse(parts=[TextPart(content=expected)])
            )
        )
        deps = InlineSuggestDeps(text_before="He walked into the hall,")
        result = await agent.run(prompt="Continue", deps=deps)
        assert result == expected

    @pytest.mark.asyncio
    async def test_agent_with_empty_text_before(self) -> None:
        """Edge case: empty text_before still produces output."""
        agent = InlineSuggestAgent(model=TestModel())
        deps = InlineSuggestDeps(text_before="")
        result = await agent.run(prompt="Start writing.", deps=deps)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_agent_with_long_text_before(self) -> None:
        """Edge case: long text_before still works."""
        long_text = "The wind howled through the narrow streets. " * 50
        agent = InlineSuggestAgent(model=TestModel())
        deps = InlineSuggestDeps(text_before=long_text)
        result = await agent.run(prompt="Continue", deps=deps)
        assert isinstance(result, str)
