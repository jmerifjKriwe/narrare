"""Tests for CharacterVoiceDriftAgent — instantiation + RULE-02b Mode-1 loading.

Split layout (the file ends in ``_agent.py`` so check_architecture applies the
200-line agent limit — cf. the CharacterVoiceCheckerAgent test split):
- this file — instantiation, RULE-02b Mode-1 template loading, the end-to-end
  FunctionModel run (single strict output, ``final_result`` tool), and the
  PromptComposer Mode-1 resolution test
- test_character_voice_drift_agent_validation.py — ADR-035 validator invariants
- test_character_voice_drift_types.py — types + Decision-5 (no rewrite/profile)

No real LLM calls (RULE-01b).
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from narrare_core.agents.character_voice_drift_agent import (
    CharacterVoiceDriftAgent,
)
from narrare_core.agents.character_voice_drift_types import (
    CharacterVoiceDriftDeps,
    VoiceDriftResult,
)
from narrare_core.llm import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry


def _underlying_agent(agent: CharacterVoiceDriftAgent) -> Any:
    """Return the wrapped pydantic-ai agent.

    Single point of private access (RULE-23): one suppression for the module
    instead of one per test touching the internals.
    """
    return agent._agent  # type: ignore[reportPrivateUsage]


@pytest.fixture()
def agent() -> CharacterVoiceDriftAgent:
    return CharacterVoiceDriftAgent(model=TestModel())


class TestCharacterVoiceDriftAgentInstantiation:
    """CharacterVoiceDriftAgent instantiates correctly."""

    def test_can_be_instantiated(self) -> None:
        agent = CharacterVoiceDriftAgent(model=TestModel())
        assert isinstance(agent, CharacterVoiceDriftAgent)

    def test_instantiated_with_system_prompt(self) -> None:
        """The governed voice_drift template is passed as system_prompt (Mode 1)."""
        agent = CharacterVoiceDriftAgent(
            model=TestModel(),
            system_prompt="You are a character-voice drift classifier.",
        )
        assert isinstance(agent, CharacterVoiceDriftAgent)

    def test_instantiated_without_system_prompt(self) -> None:
        """Agent can be instantiated without a system_prompt (tests, fallback)."""
        agent = CharacterVoiceDriftAgent(model=TestModel(), system_prompt=None)
        assert isinstance(agent, CharacterVoiceDriftAgent)

    def test_mode1_system_prompt_is_passed_through_unchanged(self) -> None:
        """RULE-02b: the agent passes the resolved template verbatim — no inline.

        The agent must NOT synthesise or inline a system prompt; it forwards the
        Mode-1-resolved governed ``voice_drift`` template to pydantic-ai exactly
        as received. Verified by inspecting the underlying ``_agent``'s system
        prompt store (the Layer-3 service resolves the real template via
        PromptComposer).
        """
        resolved_template = "## System Prompt\n\nYou are a character-voice drift classifier."
        agent = CharacterVoiceDriftAgent(
            model=TestModel(),
            system_prompt=resolved_template,
        )
        sys_prompts = _underlying_agent(agent)._system_prompts
        assert resolved_template in sys_prompts

    def test_no_system_prompt_when_none(self) -> None:
        """When system_prompt is None, no static prompt is injected by the agent."""
        agent = CharacterVoiceDriftAgent(model=TestModel(), system_prompt=None)
        sys_prompts = _underlying_agent(agent)._system_prompts
        assert not sys_prompts

    def test_output_validator_registered(self) -> None:
        """ADR-035: an output validator is registered on the underlying agent."""
        agent = CharacterVoiceDriftAgent(model=TestModel())
        assert len(_underlying_agent(agent)._output_validators) >= 1

    def test_inherits_run_stream_from_base(self) -> None:
        """RULE-13 (ADR-065): the two-method run/stream interface is provided.

        ``run()`` is overridden (returns VoiceDriftResult); ``run_stream()`` is
        inherited from NarrareAgent — mirrors the sibling CharacterVoiceAgent /
        CharacterVoiceCheckerAgent.
        """
        agent = CharacterVoiceDriftAgent(model=TestModel())
        assert callable(agent.run)
        assert callable(agent.run_stream)


# ---------------------------------------------------------------------------
# Agent run — end-to-end (FunctionModel drives a valid structured response)
# ---------------------------------------------------------------------------


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
                                "formality declines consistently from ch-3 through ch-12",
                                "type-token ratio jumps sharply at ch-7",
                            ],
                            "per_chapter_notes": [
                                {"chapter_id": "ch-7", "note": "Sharp TTR jump."},
                                {"chapter_id": "ch-11", "note": "Lowest match score."},
                            ],
                            "suggested_attention": ["ch-7", "ch-11"],
                        },
                    )
                ]
            )
        )
        agent = CharacterVoiceDriftAgent(model=model)
        result = await agent.run(
            prompt="Character: Elena\nTrend:\nch-1: 92 stable\n...",
            deps=CharacterVoiceDriftDeps(character_name="Elena"),
        )
        assert isinstance(result, VoiceDriftResult)
        assert result.drift_type == "inconsistency"
        assert result.confidence == 0.82
        assert len(result.longitudinal_reasons) == 2
        assert len(result.per_chapter_notes) == 2
        assert result.per_chapter_notes[0].chapter_id == "ch-7"
        assert result.suggested_attention == ["ch-7", "ch-11"]

    @pytest.mark.asyncio
    async def test_run_with_mode1_system_prompt_end_to_end(self) -> None:
        """RULE-02b: the resolved voice_drift template flows through to the run.

        The agent accepts the Mode-1-resolved governed template as system_prompt
        and the end-to-end run still produces structured output — proving the
        template is forwarded to pydantic-ai without inline mutation.
        """
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
        agent = CharacterVoiceDriftAgent(
            model=model,
            system_prompt="## System Prompt\n\nYou are a voice drift classifier.",
        )
        result = await agent.run(
            prompt="Character: Marc\nTrend:\nch-1: 95 stable\nch-2: 88 minor\n...",
            deps=CharacterVoiceDriftDeps(character_name="Marc"),
        )
        assert result.drift_type == "evolution"
        assert result.confidence == 0.74


class TestPromptComposerMode1Resolution:
    """ADR-046 §D.1 — the agent's system prompt resolves via PromptComposer Mode 1.

    Proves the agent is wired to receive the governed ``voice_drift`` template
    through PromptComposer (no inline fallback, no app-layer loader). The
    composed system prompt is then forwarded to the agent constructor verbatim
    (RULE-02b).
    """

    @pytest.mark.asyncio
    async def test_composer_resolves_voice_drift_template_for_agent(self) -> None:
        registry = PromptRegistry()
        composer = PromptComposer(registry)
        ctx = PromptContext(
            language="en",
            mode="voice_drift",
            writing_language="en",
            project_title="Echoes of the Thornwall",
            genre="Fantasy",
            user_preferences="Concise prose.",
            avoidance_patterns="Cliches.",
            extra={"kb_characters": "Elena; Mara"},
        )
        result = await composer.build(LLMIntent.VOICE, ctx)

        # The composed system prompt carries the governed drift template's
        # distinctive instruction (a longitudinal trend classifier) — proving
        # Mode-1 resolution, not an inline fallback.
        assert "drift" in result.system.lower()
        assert "Echoes of the Thornwall" in result.system
        assert "{{writing_language}}" not in result.system
        assert "{{kb_characters}}" not in result.system

        # The agent forwards this resolved template verbatim as its system
        # prompt (RULE-02b — no inline mutation).
        agent = CharacterVoiceDriftAgent(
            model=TestModel(),
            system_prompt=result.system,
        )
        sys_prompts = _underlying_agent(agent)._system_prompts
        assert result.system in sys_prompts
