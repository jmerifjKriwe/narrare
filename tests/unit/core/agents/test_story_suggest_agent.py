"""Tests for StorySuggestAgent — instantiation and execution.

Split from test_story_suggest_types.py per RULE-04 (file size limit).
Output model tests live in test_story_suggest_types.py.

Test strategy:
- FunctionModel for deterministic structured-output tests (no real LLM — RULE-01b)

See WRITE-009 (Writer's Unblock Tools).
"""

from __future__ import annotations

import json

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from narrare_core.agents.story_suggest_agent import StorySuggestAgent
from narrare_core.agents.story_suggest_types import (
    StorySuggestDeps,
    StorySuggestion,
    StorySuggestionType,
    StorySuggestOutput,
)


def _story_suggest_response(suggestions: list[dict[str, str]]) -> ModelResponse:
    """Build a FunctionModel ModelResponse carrying a StorySuggestOutput tool call."""
    payload = {"suggestions": suggestions}
    return ModelResponse(parts=[ToolCallPart(tool_name="final_result", args=json.dumps(payload))])


# ---------------------------------------------------------------------------
# C. StorySuggestAgent — Instantiation
# ---------------------------------------------------------------------------


class TestStorySuggestAgentInstantiation:
    """StorySuggestAgent instantiates correctly with TestModel."""

    def test_agent_creates_successfully(self) -> None:
        """Agent can be instantiated with TestModel."""
        agent = StorySuggestAgent(model=TestModel())
        assert isinstance(agent, StorySuggestAgent)

    def test_agent_system_prompt_key(self) -> None:
        """SYSTEM_PROMPT_KEY is set to 'story_suggest'."""
        assert StorySuggestAgent.SYSTEM_PROMPT_KEY == "story_suggest"

    def test_agent_with_system_prompt(self) -> None:
        """Agent can receive a system_prompt (from PromptComposer)."""
        agent = StorySuggestAgent(
            model=TestModel(),
            system_prompt="You are a creative writing consultant.",
        )
        assert isinstance(agent, StorySuggestAgent)


# ---------------------------------------------------------------------------
# D. StorySuggestAgent — Execution
# ---------------------------------------------------------------------------


class TestStorySuggestAgentExecution:
    """StorySuggestAgent runs and returns StorySuggestOutput."""

    @pytest.mark.asyncio
    async def test_agent_returns_structured_output(self) -> None:
        """FunctionModel returns a structured StorySuggestOutput."""
        suggestions_data = [
            {
                "type": "plot_development",
                "title": "The Betrayal",
                "description": "A trusted ally reveals their true allegiance.",
                "connection": "Foreshadowed by the ally's hesitation in Chapter 2.",
            },
            {
                "type": "character_moment",
                "title": "A Quiet Confession",
                "description": "The protagonist admits their deepest fear.",
                "connection": "Develops the vulnerability hinted at in Chapter 1.",
            },
        ]
        agent = StorySuggestAgent(
            model=FunctionModel(lambda messages, info: _story_suggest_response(suggestions_data))
        )
        deps = StorySuggestDeps(
            project_title="The Last Kingdom", genre="Fantasy", writing_language="en"
        )
        result = await agent.run(
            prompt="I'm stuck after the protagonist enters the forest.", deps=deps
        )
        assert isinstance(result, StorySuggestOutput)
        assert len(result.suggestions) == 2
        assert isinstance(result.suggestions[0], StorySuggestion)
        assert result.suggestions[0].type == StorySuggestionType.PLOT_DEVELOPMENT
        assert result.suggestions[0].title == "The Betrayal"
        assert result.suggestions[1].type == StorySuggestionType.CHARACTER_MOMENT

    @pytest.mark.asyncio
    async def test_agent_with_default_deps(self) -> None:
        """Agent works with default (empty) deps."""
        agent = StorySuggestAgent(
            model=FunctionModel(
                lambda messages, info: _story_suggest_response(
                    [
                        {
                            "type": "world_detail",
                            "title": "The Ancient Ruins",
                            "description": "Weathered stones mark a forgotten civilisation.",
                            "connection": "Explains the strange symbols from Chapter 4.",
                        },
                    ]
                )
            )
        )
        deps = StorySuggestDeps()
        result = await agent.run(prompt="Give me a world-building idea.", deps=deps)
        assert isinstance(result, StorySuggestOutput)
        assert len(result.suggestions) == 1
        assert result.suggestions[0].type == StorySuggestionType.WORLD_DETAIL

    @pytest.mark.asyncio
    async def test_agent_returns_empty_suggestions(self) -> None:
        """Agent can return an empty suggestions list."""
        agent = StorySuggestAgent(
            model=FunctionModel(lambda messages, info: _story_suggest_response([]))
        )
        deps = StorySuggestDeps(project_title="Test", genre="Sci-Fi")
        result = await agent.run(prompt="Suggest something.", deps=deps)
        assert isinstance(result, StorySuggestOutput)
        assert result.suggestions == []

    @pytest.mark.asyncio
    async def test_agent_all_suggestion_types(self) -> None:
        """Agent handles all five suggestion types in one response."""
        suggestions_data = [
            {"type": t, "title": f"Title {t}", "description": "desc", "connection": "conn"}
            for t in (
                "plot_development",
                "character_moment",
                "dialogue_option",
                "world_detail",
                "stylistic_alternative",
            )
        ]
        agent = StorySuggestAgent(
            model=FunctionModel(lambda messages, info: _story_suggest_response(suggestions_data))
        )
        deps = StorySuggestDeps(project_title="Test", genre="Fantasy", writing_language="en")
        result = await agent.run(prompt="Give me five suggestions.", deps=deps)
        assert isinstance(result, StorySuggestOutput)
        assert len(result.suggestions) == 5
        types = {s.type for s in result.suggestions}
        assert types == {
            StorySuggestionType.PLOT_DEVELOPMENT,
            StorySuggestionType.CHARACTER_MOMENT,
            StorySuggestionType.DIALOGUE_OPTION,
            StorySuggestionType.WORLD_DETAIL,
            StorySuggestionType.STYLISTIC_ALTERNATIVE,
        }
