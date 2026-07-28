"""Tests for AuthorVoiceDriftAgent._process_output + end-to-end run
(ANAL-009 Phase 2B / ADR-074).

Mirrors ``test_character_voice_drift_process_output.py``. The output function
structures the LLM response into the REUSED
:class:`VoiceDriftResult`. Also includes the PromptComposer Mode-1 resolution
test (ADR-046 §D.1) proving the agent's system prompt resolves through the
governed ``author_voice_drift`` template when wired via PromptComposer (no
inline fallback). No real LLM calls (RULE-01b).
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
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


def _make_ctx(
    deps: AuthorVoiceDriftDeps | None = None,
) -> RunContext[AuthorVoiceDriftDeps]:
    return RunContext[AuthorVoiceDriftDeps](
        deps=deps or AuthorVoiceDriftDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


class TestAuthorVoiceDriftProcessOutput:
    """The _process_output output function structures the LLM response."""

    @pytest.mark.asyncio
    async def test_process_output_returns_result(self) -> None:
        agent = AuthorVoiceDriftAgent(model=TestModel())
        ctx = _make_ctx(AuthorVoiceDriftDeps(writing_language="en"))
        result = await agent._process_output(  # type: ignore[reportPrivateUsage]
            ctx,
            drift_type="inconsistency",
            confidence=0.82,
            longitudinal_reasons=[
                "dialogue_ratio rises sharply from ch-3 through ch-12",
                "description_density jumps at ch-7",
            ],
            per_chapter_notes=[
                {"chapter_id": "ch-7", "note": "Density jump."},
                {"chapter_id": "ch-11", "note": "Lowest match score."},
            ],
            suggested_attention=["ch-7", "ch-11"],
        )
        assert isinstance(result, VoiceDriftResult)
        assert result.drift_type == "inconsistency"
        assert result.confidence == 0.82
        assert len(result.longitudinal_reasons) == 2
        assert result.per_chapter_notes[0].chapter_id == "ch-7"
        assert result.suggested_attention == ["ch-7", "ch-11"]

    @pytest.mark.asyncio
    async def test_process_output_with_defaults(self) -> None:
        agent = AuthorVoiceDriftAgent(model=TestModel())
        result = await agent._process_output(_make_ctx())
        assert isinstance(result, VoiceDriftResult)
        assert result.drift_type == "evolution"
        assert result.confidence == 0.0
        assert result.longitudinal_reasons == []
        assert result.per_chapter_notes == []
        assert result.suggested_attention == []

    @pytest.mark.asyncio
    async def test_process_output_uses_defaults_for_omitted_fields(self) -> None:
        agent = AuthorVoiceDriftAgent(model=TestModel())
        result = await agent._process_output(_make_ctx(), drift_type="context", confidence=0.55)
        assert result.drift_type == "context"
        assert result.confidence == 0.55
        assert result.longitudinal_reasons == []


class TestProcessOutputStreaming:
    """During streaming (ctx.partial_output set) the output function returns empty."""

    @pytest.mark.asyncio
    async def test_partial_output_returns_empty_result(self) -> None:
        agent = AuthorVoiceDriftAgent(model=TestModel())
        ctx = RunContext[AuthorVoiceDriftDeps](
            deps=AuthorVoiceDriftDeps(),
            model=TestModel(),
            usage=RunUsage(),
            partial_output=True,
        )
        result = await agent._process_output(  # type: ignore[reportPrivateUsage]
            ctx,
            drift_type="inconsistency",
            confidence=0.9,
            longitudinal_reasons=["a reason"],
        )
        assert isinstance(result, VoiceDriftResult)
        assert result.confidence == 0.0
        assert result.longitudinal_reasons == []


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
        sys_prompts = agent._agent._system_prompts  # type: ignore[reportPrivateUsage]
        assert result.system in sys_prompts
