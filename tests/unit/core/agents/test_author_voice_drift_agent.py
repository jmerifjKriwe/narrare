"""Tests for AuthorVoiceDriftAgent — instantiation, end-to-end run, and
RULE-02b Mode-1 loading (ANAL-009 Phase 2B / ADR-074).

Mirrors the CharacterVoiceDriftAgent test split layout. This file covers
instantiation + end-to-end run() via FunctionModel (single ``final_result``
output tool) + RULE-02b Mode-1 template loading (the governed
``author_voice_drift`` template). Sibling file covers the ADR-035 validator
(``test_author_voice_drift_agent_validation.py``).

No real LLM calls (RULE-01b).
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from narrare_core.agents.author_voice_drift_agent import AuthorVoiceDriftAgent
from narrare_core.agents.author_voice_drift_types import AuthorVoiceDriftDeps
from narrare_core.agents.character_voice_drift_types import VoiceDriftResult
from narrare_core.llm import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry


def _underlying_agent(agent: AuthorVoiceDriftAgent) -> Any:
    """Return the wrapped pydantic-ai agent.

    Single point of private access (RULE-23): one suppression for the module
    instead of one per test touching the internals.
    """
    return agent._agent  # type: ignore[reportPrivateUsage]


@pytest.fixture()
def agent() -> AuthorVoiceDriftAgent:
    return AuthorVoiceDriftAgent(model=TestModel())


class TestAuthorVoiceDriftAgentInstantiation:
    """AuthorVoiceDriftAgent instantiates correctly."""

    def test_can_be_instantiated(self) -> None:
        agent = AuthorVoiceDriftAgent(model=TestModel())
        assert isinstance(agent, AuthorVoiceDriftAgent)

    def test_instantiated_with_system_prompt(self) -> None:
        """The governed author_voice_drift template is passed as system_prompt (Mode 1)."""
        agent = AuthorVoiceDriftAgent(
            model=TestModel(),
            system_prompt="You are an author-voice drift classifier.",
        )
        assert isinstance(agent, AuthorVoiceDriftAgent)

    def test_instantiated_without_system_prompt(self) -> None:
        agent = AuthorVoiceDriftAgent(model=TestModel(), system_prompt=None)
        assert isinstance(agent, AuthorVoiceDriftAgent)

    def test_mode1_system_prompt_is_passed_through_unchanged(self) -> None:
        """RULE-02b: the agent forwards the resolved template verbatim — no inline.

        The agent must NOT synthesise or inline a system prompt; it forwards the
        Mode-1-resolved governed ``author_voice_drift`` template to pydantic-ai
        exactly as received (the Layer-3 service resolves the real template via
        PromptComposer).
        """
        resolved_template = "## System Prompt\n\nYou are an author-voice drift classifier."
        agent = AuthorVoiceDriftAgent(
            model=TestModel(),
            system_prompt=resolved_template,
        )
        sys_prompts = _underlying_agent(agent)._system_prompts
        assert resolved_template in sys_prompts

    def test_no_system_prompt_when_none(self) -> None:
        agent = AuthorVoiceDriftAgent(model=TestModel(), system_prompt=None)
        sys_prompts = _underlying_agent(agent)._system_prompts
        assert not sys_prompts

    def test_output_validator_registered(self) -> None:
        """ADR-035: an output validator is registered on the underlying agent."""
        agent = AuthorVoiceDriftAgent(model=TestModel())
        assert len(_underlying_agent(agent)._output_validators) >= 1

    def test_inherits_run_stream_from_base(self) -> None:
        """RULE-13 (ADR-065): the two-method run/stream interface is provided."""
        agent = AuthorVoiceDriftAgent(model=TestModel())
        assert callable(agent.run)
        assert callable(agent.run_stream)


class TestAgentRunEndToEnd:
    """agent.run() returns structured VoiceDriftResult (FunctionModel)."""

    @pytest.mark.asyncio
    async def test_run_returns_result_end_to_end(self) -> None:
        model = FunctionModel(
            lambda messages, info: ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result",
                        args={
                            "drift_type": "inconsistency",
                            "confidence": 0.82,
                            "longitudinal_reasons": [
                                "dialogue_ratio rises sharply from ch-3",
                            ],
                            "per_chapter_notes": [{"chapter_id": "ch-7", "note": "Density jump."}],
                            "suggested_attention": ["ch-7"],
                        },
                    )
                ]
            )
        )
        agent = AuthorVoiceDriftAgent(model=model)
        result = await agent.run(
            prompt="Narrator trend:\nch-1: 92 stable\n...",
            deps=AuthorVoiceDriftDeps(),
        )
        assert isinstance(result, VoiceDriftResult)
        assert result.drift_type == "inconsistency"
        assert result.confidence == 0.82
        assert result.suggested_attention == ["ch-7"]

    @pytest.mark.asyncio
    async def test_run_with_mode1_system_prompt_end_to_end(self) -> None:
        """RULE-02b: the resolved author_voice_drift template flows through."""
        model = FunctionModel(
            lambda messages, info: ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result",
                        args={
                            "drift_type": "evolution",
                            "confidence": 0.74,
                            "longitudinal_reasons": ["register gradually elevates across the arc"],
                            "per_chapter_notes": [],
                            "suggested_attention": [],
                        },
                    )
                ]
            )
        )
        agent = AuthorVoiceDriftAgent(
            model=model,
            system_prompt="## System Prompt\n\nYou are an author-voice drift classifier.",
        )
        result = await agent.run(
            prompt="Narrator trend:\nch-1: 95 stable\nch-2: 88 minor\n...",
            deps=AuthorVoiceDriftDeps(),
        )
        assert result.drift_type == "evolution"
        assert result.confidence == 0.74


class TestPromptComposerMode1Resolution:
    """ADR-046 §D.1 — the agent's system prompt resolves via PromptComposer Mode 1."""

    @pytest.mark.asyncio
    async def test_composer_resolves_author_voice_drift_template_for_agent(self) -> None:
        registry = PromptRegistry()
        composer = PromptComposer(registry)
        ctx = PromptContext(
            language="en",
            mode="author_voice_drift",
            writing_language="en",
            project_title="Echoes of the Thornwall",
            genre="Fantasy",
            user_preferences="Concise prose.",
            avoidance_patterns="Cliches.",
            extra={"kb_characters": "Elena; Mara"},
        )
        result = await composer.build(LLMIntent.VOICE, ctx)

        # The composed system prompt carries the governed author-voice-drift
        # template's distinctive instruction — proving Mode-1 resolution.
        assert "narrator" in result.system.lower() or "author" in result.system.lower()
        assert "drift" in result.system.lower()
        assert "Echoes of the Thornwall" in result.system
        assert "{{writing_language}}" not in result.system

        agent = AuthorVoiceDriftAgent(model=TestModel(), system_prompt=result.system)
        sys_prompts = _underlying_agent(agent)._system_prompts
        assert result.system in sys_prompts
