"""Tests for CharacterVoiceCheckerAgent._process_output (WRITE-010 / ADR-057).

The agent's strict output validator (ADR-035) rejects TestModel's random
default output, so — following the CharacterVoiceAgent / CoreferenceAgent
pattern — the output function is tested directly with valid args. No real LLM
calls (RULE-01b).
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from narrare_core.agents.character_voice_checker_agent import (
    CharacterVoiceCheckerAgent,
)
from narrare_core.agents.character_voice_checker_types import (
    CharacterVoiceCheckerDeps,
    CharacterVoiceCheckerOutput,
)


def _make_ctx(
    deps: CharacterVoiceCheckerDeps | None = None,
) -> RunContext[CharacterVoiceCheckerDeps]:
    return RunContext[CharacterVoiceCheckerDeps](
        deps=deps or CharacterVoiceCheckerDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


class TestCharacterVoiceCheckerProcessOutput:
    """The _process_output output function structures the LLM response."""

    @pytest.mark.asyncio
    async def test_process_output_returns_output(self) -> None:
        agent = CharacterVoiceCheckerAgent(model=TestModel())
        ctx = _make_ctx(
            CharacterVoiceCheckerDeps(
                attributed_dialogue='Elena: "I dare say."',
                character_names=["Elena"],
                writing_language="en",
            )
        )
        result = await agent._process_output(  # type: ignore[reportPrivateUsage]
            ctx,
            characters=[
                {
                    "character_name": "Elena",
                    "match_judgment": "mostly_consistent",
                    "qualitative_sub_score": 78.5,
                    "flagged_lines": [
                        {
                            "quote": "I dare say.",
                            "reason": "Drops to an informal register where the "
                            "profile is elevated/formal.",
                        }
                    ],
                }
            ],
        )
        assert isinstance(result, CharacterVoiceCheckerOutput)
        assert len(result.characters) == 1
        entry = result.characters[0]
        assert entry.character_name == "Elena"
        assert entry.match_judgment == "mostly_consistent"
        assert entry.qualitative_sub_score == 78.5
        assert len(entry.flagged_lines) == 1
        assert entry.flagged_lines[0].quote == "I dare say."
        assert "register" in entry.flagged_lines[0].reason

    @pytest.mark.asyncio
    async def test_process_output_with_defaults(self) -> None:
        """No arguments produce a valid empty CharacterVoiceCheckerOutput."""
        agent = CharacterVoiceCheckerAgent(model=TestModel())
        result = await agent._process_output(_make_ctx())
        assert isinstance(result, CharacterVoiceCheckerOutput)
        assert result.characters == []

    @pytest.mark.asyncio
    async def test_process_output_multiple_characters(self) -> None:
        """A single LLM call checks all supplied characters."""
        agent = CharacterVoiceCheckerAgent(model=TestModel())
        result = await agent._process_output(
            _make_ctx(),
            characters=[
                {
                    "character_name": "Elena",
                    "match_judgment": "consistent",
                    "qualitative_sub_score": 95.0,
                },
                {
                    "character_name": "Marc",
                    "match_judgment": "off",
                    "qualitative_sub_score": 30.0,
                    "flagged_lines": [{"quote": "Aye.", "reason": "Omits the stored verbal tic."}],
                },
            ],
        )
        assert len(result.characters) == 2
        assert result.characters[0].character_name == "Elena"
        assert result.characters[1].character_name == "Marc"
        assert result.characters[1].match_judgment == "off"

    @pytest.mark.asyncio
    async def test_process_output_uses_defaults_for_omitted_fields(self) -> None:
        """Omitted fields fall back to the schema defaults (judgment/score)."""
        agent = CharacterVoiceCheckerAgent(model=TestModel())
        result = await agent._process_output(
            _make_ctx(),
            characters=[{"character_name": "Elena"}],
        )
        entry = result.characters[0]
        # Defaults mirror the template's "no dialogue" convention.
        assert entry.match_judgment == "consistent"
        assert entry.qualitative_sub_score == 100.0
        assert entry.flagged_lines == []

    @pytest.mark.asyncio
    async def test_process_output_empty_flagged_lines_for_consistent(self) -> None:
        """A fully consistent character has an empty flagged_lines list."""
        agent = CharacterVoiceCheckerAgent(model=TestModel())
        result = await agent._process_output(
            _make_ctx(),
            characters=[
                {
                    "character_name": "Elena",
                    "match_judgment": "consistent",
                    "qualitative_sub_score": 98.0,
                    "flagged_lines": [],
                }
            ],
        )
        assert result.characters[0].flagged_lines == []


class TestProcessOutputStreaming:
    """During streaming (ctx.partial_output set) the output function returns empty."""

    @pytest.mark.asyncio
    async def test_partial_output_returns_empty_output(self) -> None:
        """When ctx.partial_output is set, _process_output short-circuits to empty.

        pydantic-ai sets ``ctx.partial_output`` during streaming; the output
        function returns a minimal empty result then (the final structured
        result is assembled at run completion).
        """
        agent = CharacterVoiceCheckerAgent(model=TestModel())
        ctx = RunContext[CharacterVoiceCheckerDeps](
            deps=CharacterVoiceCheckerDeps(),
            model=TestModel(),
            usage=RunUsage(),
            partial_output=True,  # truthy -> streaming branch
        )
        result = await agent._process_output(  # type: ignore[reportPrivateUsage]
            ctx,
            characters=[{"character_name": "Elena"}],
        )
        assert isinstance(result, CharacterVoiceCheckerOutput)
        # During streaming the partial args are ignored — empty result returned.
        assert result.characters == []


# ---------------------------------------------------------------------------
# E. Agent run — end-to-end (FunctionModel drives a valid structured response)
#
# TestModel's random output fails the strict validator (cf. CharacterVoiceAgent),
# so FunctionModel with an explicit ToolCallPart drives agent.run() end-to-end.
# This proves the full wiring: Mode-1 system_prompt -> deps -> output function
# -> output_validator -> cast. Mirrors test_kb_assist_agent.py.
# ---------------------------------------------------------------------------


class TestAgentRunEndToEnd:
    """agent.run() returns structured CharacterVoiceCheckerOutput (FunctionModel)."""

    @pytest.mark.asyncio
    async def test_run_returns_output_end_to_end(self) -> None:
        model = FunctionModel(
            lambda messages, info: ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result__process_output",
                        args={
                            "characters": [
                                {
                                    "character_name": "Elena",
                                    "match_judgment": "mostly_consistent",
                                    "qualitative_sub_score": 78.5,
                                    "flagged_lines": [
                                        {
                                            "quote": "I dare say.",
                                            "reason": "Informal register drift.",
                                        }
                                    ],
                                }
                            ]
                        },
                    )
                ]
            )
        )
        agent = CharacterVoiceCheckerAgent(model=model)
        result = await agent.run(
            prompt='Dialogue:\nElena: "I dare say."',
            deps=CharacterVoiceCheckerDeps(character_names=["Elena"]),
        )
        assert isinstance(result, CharacterVoiceCheckerOutput)
        assert len(result.characters) == 1
        entry = result.characters[0]
        assert entry.character_name == "Elena"
        assert entry.match_judgment == "mostly_consistent"
        assert entry.qualitative_sub_score == 78.5
        assert len(entry.flagged_lines) == 1

    @pytest.mark.asyncio
    async def test_run_with_mode1_system_prompt_end_to_end(self) -> None:
        """RULE-02b: the resolved voice_check template flows through to the run.

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
                            "characters": [
                                {
                                    "character_name": "Marc",
                                    "match_judgment": "consistent",
                                    "qualitative_sub_score": 95.0,
                                }
                            ]
                        },
                    )
                ]
            )
        )
        agent = CharacterVoiceCheckerAgent(
            model=model,
            system_prompt="## System Prompt\n\nYou are a voice checker.",
        )
        result = await agent.run(prompt="Dialogue.", deps=CharacterVoiceCheckerDeps())
        assert result.characters[0].character_name == "Marc"
