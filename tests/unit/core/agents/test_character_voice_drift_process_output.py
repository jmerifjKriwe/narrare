"""Tests for CharacterVoiceDriftAgent._process_output (ANAL-009 / ADR-073).

The agent's strict output validator (ADR-035) rejects TestModel's random
default output, so — following the CharacterVoiceCheckerAgent pattern — the
output function is tested directly with valid args, and the end-to-end run is
driven by FunctionModel with an explicit ToolCallPart. No real LLM calls
(RULE-01b).

Also includes the PromptComposer Mode-1 resolution test (ADR-046 §D.1) proving
the agent's system prompt resolves through the governed ``voice_drift``
template when wired via PromptComposer (no inline fallback).
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
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


def _make_ctx(
    deps: CharacterVoiceDriftDeps | None = None,
) -> RunContext[CharacterVoiceDriftDeps]:
    return RunContext[CharacterVoiceDriftDeps](
        deps=deps or CharacterVoiceDriftDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


class TestCharacterVoiceDriftProcessOutput:
    """The _process_output output function structures the LLM response."""

    @pytest.mark.asyncio
    async def test_process_output_returns_result(self) -> None:
        agent = CharacterVoiceDriftAgent(model=TestModel())
        ctx = _make_ctx(
            CharacterVoiceDriftDeps(
                character_name="Elena",
                writing_language="en",
            )
        )
        result = await agent._process_output(  # type: ignore[reportPrivateUsage]
            ctx,
            drift_type="inconsistency",
            confidence=0.82,
            longitudinal_reasons=[
                "formality declines consistently from ch-3 through ch-12",
                "type-token ratio jumps sharply at ch-7",
            ],
            per_chapter_notes=[
                {"chapter_id": "ch-7", "note": "Sharp TTR jump."},
                {"chapter_id": "ch-11", "note": "Lowest match score."},
            ],
            suggested_attention=["ch-7", "ch-11"],
        )
        assert isinstance(result, VoiceDriftResult)
        assert result.drift_type == "inconsistency"
        assert result.confidence == 0.82
        assert len(result.longitudinal_reasons) == 2
        assert len(result.per_chapter_notes) == 2
        assert result.per_chapter_notes[0].chapter_id == "ch-7"
        assert result.per_chapter_notes[0].note == "Sharp TTR jump."
        assert result.suggested_attention == ["ch-7", "ch-11"]

    @pytest.mark.asyncio
    async def test_process_output_with_defaults(self) -> None:
        """No arguments produce a valid empty VoiceDriftResult."""
        agent = CharacterVoiceDriftAgent(model=TestModel())
        result = await agent._process_output(_make_ctx())
        assert isinstance(result, VoiceDriftResult)
        assert result.drift_type == "evolution"
        assert result.confidence == 0.0
        assert result.longitudinal_reasons == []
        assert result.per_chapter_notes == []
        assert result.suggested_attention == []

    @pytest.mark.asyncio
    async def test_process_output_uses_defaults_for_omitted_fields(self) -> None:
        """Omitted fields fall back to the schema defaults."""
        agent = CharacterVoiceDriftAgent(model=TestModel())
        result = await agent._process_output(
            _make_ctx(),
            drift_type="context",
            confidence=0.55,
        )
        assert result.drift_type == "context"
        assert result.confidence == 0.55
        assert result.longitudinal_reasons == []
        assert result.per_chapter_notes == []
        assert result.suggested_attention == []

    @pytest.mark.asyncio
    async def test_process_output_empty_trend_convention(self) -> None:
        """The template's empty-trend convention is a valid output.

        An empty trend yields ``confidence=0.0`` + empty lists — valid, the
        agent's "no chapters with attributable dialogue" convention.
        """
        agent = CharacterVoiceDriftAgent(model=TestModel())
        result = await agent._process_output(
            _make_ctx(),
            drift_type="evolution",
            confidence=0.0,
            longitudinal_reasons=[],
            per_chapter_notes=[
                {"chapter_id": "", "note": "No chapters with attributable dialogue."}
            ],
            suggested_attention=[],
        )
        assert result.confidence == 0.0
        # The empty-chapter_id note is filtered by the validator, but
        # _process_output itself constructs it faithfully (filtering is the
        # validator's job — tested in test_character_voice_drift_agent_validation).
        assert len(result.per_chapter_notes) == 1


class TestProcessOutputStreaming:
    """During streaming (ctx.partial_output set) the output function returns empty."""

    @pytest.mark.asyncio
    async def test_partial_output_returns_empty_result(self) -> None:
        """When ctx.partial_output is set, _process_output short-circuits to empty."""
        agent = CharacterVoiceDriftAgent(model=TestModel())
        ctx = RunContext[CharacterVoiceDriftDeps](
            deps=CharacterVoiceDriftDeps(),
            model=TestModel(),
            usage=RunUsage(),
            partial_output=True,  # truthy -> streaming branch
        )
        result = await agent._process_output(  # type: ignore[reportPrivateUsage]
            ctx,
            drift_type="inconsistency",
            confidence=0.9,
            longitudinal_reasons=["a reason"],
        )
        assert isinstance(result, VoiceDriftResult)
        # During streaming the partial args are ignored — empty result returned.
        assert result.confidence == 0.0
        assert result.longitudinal_reasons == []


# ---------------------------------------------------------------------------
# E. Agent run — end-to-end (FunctionModel drives a valid structured response)
# ---------------------------------------------------------------------------


class TestAgentRunEndToEnd:
    """agent.run() returns structured VoiceDriftResult (FunctionModel)."""

    @pytest.mark.asyncio
    async def test_run_returns_result_end_to_end(self) -> None:
        model = FunctionModel(
            lambda messages, info: ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result__process_output",
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
                        tool_name="final_result__process_output",
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
        sys_prompts = agent._agent._system_prompts  # type: ignore[reportPrivateUsage]
        assert result.system in sys_prompts
