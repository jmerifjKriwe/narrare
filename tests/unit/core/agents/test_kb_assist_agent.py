"""Tests for KBAssistAgent — instantiation, deps, agent run.

Test strategy:
- FunctionModel with ToolCallPart for agent run tests
  (TestModel cannot produce valid Literal values)
- TestModel for instantiation tests
- No real LLM calls (RULE-01b)

The single strict output type registers one output tool named
``final_result`` (pydantic-ai 2.x single-model naming).

See also: test_kb_assist_validation.py — _validate_output tests
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from narrare_core.agents.kb_assist_agent import KBAssistAgent, KBAssistDeps
from narrare_core.agents.kb_assist_types import KBAssistOutput

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_model() -> TestModel:
    return TestModel()


@pytest.fixture()
def agent(test_model: TestModel) -> KBAssistAgent:
    return KBAssistAgent(model=test_model)


@pytest.fixture()
def deps() -> KBAssistDeps:
    return KBAssistDeps()


@pytest.fixture()
def run_context(test_model: TestModel) -> RunContext[KBAssistDeps]:
    return RunContext[KBAssistDeps](
        deps=KBAssistDeps(),
        model=test_model,
        usage=RunUsage(),
    )


# ---------------------------------------------------------------------------
# A. Instantiation
# ---------------------------------------------------------------------------


class TestInstantiation:
    """Agent can be instantiated with and without KBAgent."""

    def test_agent_instantiation_without_kb_agent(self, test_model: TestModel) -> None:
        agent = KBAssistAgent(model=test_model)
        assert isinstance(agent, KBAssistAgent)
        assert agent._agent is not None

    def test_agent_instantiation_with_kb_agent(self, test_model: TestModel) -> None:
        """When KBAgent is provided, capabilities include ToolSearch + Toolset."""
        from narrare_core.agents.kb_agent import KBAgent

        kb_agent = KBAgent(model=test_model)
        agent = KBAssistAgent(model=test_model, kb_agent=kb_agent)
        assert isinstance(agent, KBAssistAgent)
        assert agent._agent is not None


# ---------------------------------------------------------------------------
# B. KBAssistDeps
# ---------------------------------------------------------------------------


class TestKBAssistDeps:
    """KBAssistDeps default and custom values."""

    def test_deps_default_values(self) -> None:
        deps = KBAssistDeps()
        assert deps.language == "en"
        assert deps.genre == ""
        assert deps.entity_type == ""
        assert deps.template_structure is None
        assert deps.existing_answers is None
        assert deps.world_context is None

    def test_deps_custom_values(self) -> None:
        deps = KBAssistDeps(
            language="de",
            genre="Fantasy",
            entity_type="character",
            template_structure={"fields": {"name": {"type": "string"}}},
            existing_answers={"name": "Anna"},
            world_context="A dark forest with ancient ruins.",
        )
        assert deps.language == "de"
        assert deps.genre == "Fantasy"
        assert deps.entity_type == "character"
        assert deps.template_structure == {"fields": {"name": {"type": "string"}}}
        assert deps.existing_answers == {"name": "Anna"}
        assert deps.world_context == "A dark forest with ancient ruins."


# ---------------------------------------------------------------------------
# C. Agent run — TestModel returns KBAssistOutput
# ---------------------------------------------------------------------------


class TestAgentRun:
    """Agent.run() with FunctionModel returns structured output.

    TestModel cannot produce valid Literal values for the mode parameter,
    so FunctionModel with explicit ToolCallPart is used for agent run tests.
    """

    @pytest.mark.asyncio
    async def test_run_returns_kb_assist_output_question_mode(self) -> None:
        model = FunctionModel(
            lambda messages, info: ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result",
                        args={
                            "mode": "question",
                            "question": "What is the name?",
                            "field_key": "name",
                        },
                    )
                ]
            )
        )
        agent = KBAssistAgent(model=model)
        result = await agent.run(prompt="Help me create a character", deps=KBAssistDeps())
        assert isinstance(result, KBAssistOutput)
        assert result.mode == "question"
        assert result.question == "What is the name?"

    @pytest.mark.asyncio
    async def test_run_returns_kb_assist_output_suggestion_mode(self) -> None:
        model = FunctionModel(
            lambda messages, info: ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result",
                        args={
                            "mode": "suggestion",
                            "suggestion": "A dark tower",
                            "field_key": "appearance",
                        },
                    )
                ]
            )
        )
        agent = KBAssistAgent(model=model)
        result = await agent.run(prompt="Suggest a location", deps=KBAssistDeps())
        assert result.mode == "suggestion"
        assert result.suggestion == "A dark tower"

    @pytest.mark.asyncio
    async def test_run_returns_kb_assist_output_draft_mode(self) -> None:
        model = FunctionModel(
            lambda messages, info: ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result",
                        args={"mode": "draft", "draft_entry": {"name": "Anna"}, "progress": 0.5},
                    )
                ]
            )
        )
        agent = KBAssistAgent(model=model)
        result = await agent.run(prompt="Create a character", deps=KBAssistDeps())
        assert result.mode == "draft"
        assert result.draft_entry == {"name": "Anna"}
        assert result.progress == 0.5

    @pytest.mark.asyncio
    async def test_run_returns_kb_assist_output_complete_mode(self) -> None:
        model = FunctionModel(
            lambda messages, info: ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result",
                        args={"mode": "complete", "final_entry": {"name": "Anna"}, "progress": 1.0},
                    )
                ]
            )
        )
        agent = KBAssistAgent(model=model)
        result = await agent.run(prompt="Finalize", deps=KBAssistDeps())
        assert result.mode == "complete"
        assert result.final_entry == {"name": "Anna"}
        assert result.progress == 1.0
