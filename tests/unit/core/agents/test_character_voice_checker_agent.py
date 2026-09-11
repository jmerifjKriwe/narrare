"""Tests for CharacterVoiceCheckerAgent — instantiation + Mode-1 template loading.

Split layout (the file ends in ``_agent.py`` so check_architecture applies the
200-line agent limit — cf. the CharacterVoiceAgent test split):
- this file — instantiation, RULE-02b Mode-1 template loading, and the
  end-to-end FunctionModel run (single strict output, ``final_result`` tool)
- test_character_voice_checker_agent_validation.py — ADR-035 validator invariants
- test_character_voice_checker_types.py — types + Decision-5 (no rewrite field)

No real LLM calls (RULE-01b).
"""

from __future__ import annotations

import pytest
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


@pytest.fixture()
def agent() -> CharacterVoiceCheckerAgent:
    return CharacterVoiceCheckerAgent(model=TestModel())


class TestCharacterVoiceCheckerAgentInstantiation:
    """CharacterVoiceCheckerAgent instantiates correctly."""

    def test_can_be_instantiated(self) -> None:
        agent = CharacterVoiceCheckerAgent(model=TestModel())
        assert isinstance(agent, CharacterVoiceCheckerAgent)

    def test_instantiated_with_system_prompt(self) -> None:
        """The governed voice_check template is passed as system_prompt (Mode 1)."""
        agent = CharacterVoiceCheckerAgent(
            model=TestModel(),
            system_prompt="You are a character-voice consistency checker.",
        )
        assert isinstance(agent, CharacterVoiceCheckerAgent)

    def test_instantiated_without_system_prompt(self) -> None:
        """Agent can be instantiated without a system_prompt (tests, fallback)."""
        agent = CharacterVoiceCheckerAgent(model=TestModel(), system_prompt=None)
        assert isinstance(agent, CharacterVoiceCheckerAgent)

    def test_mode1_system_prompt_is_passed_through_unchanged(self) -> None:
        """RULE-02b: the agent passes the resolved template verbatim — no inline.

        The agent must NOT synthesise or inline a system prompt; it forwards the
        Mode-1-resolved governed ``voice_check`` template to pydantic-ai exactly
        as received. Verified by inspecting the underlying ``_agent``'s system
        prompt store (the Layer-3 service resolves the real template via
        PromptComposer).
        """
        resolved_template = "## System Prompt\n\nYou are a character-voice consistency checker."
        agent = CharacterVoiceCheckerAgent(
            model=TestModel(),
            system_prompt=resolved_template,
        )
        sys_prompts = agent._agent._system_prompts  # type: ignore[reportPrivateUsage]
        assert resolved_template in sys_prompts

    def test_no_system_prompt_when_none(self) -> None:
        """When system_prompt is None, no static prompt is injected by the agent."""
        agent = CharacterVoiceCheckerAgent(model=TestModel(), system_prompt=None)
        sys_prompts = agent._agent._system_prompts  # type: ignore[reportPrivateUsage]
        # pydantic-ai stores system prompts as a tuple — assert emptiness
        # without coupling to the container type.
        assert not sys_prompts

    def test_output_validator_registered(self) -> None:
        """ADR-035: an output validator is registered on the underlying agent."""
        agent = CharacterVoiceCheckerAgent(model=TestModel())
        # pydantic-ai stores validator functions on the agent's output_validators.
        assert len(agent._agent._output_validators) >= 1  # type: ignore[reportPrivateUsage]


# ---------------------------------------------------------------------------
# Agent run — end-to-end (FunctionModel drives a valid structured response)
#
# TestModel's random output fails the strict validator (cf. CharacterVoiceAgent),
# so FunctionModel with an explicit ToolCallPart drives agent.run() end-to-end.
# This proves the full wiring: Mode-1 system_prompt -> deps -> single strict
# output tool -> output_validator. Mirrors test_kb_assist_agent.py.
# ---------------------------------------------------------------------------


class TestAgentRunEndToEnd:
    """agent.run() returns structured CharacterVoiceCheckerOutput (FunctionModel)."""

    @pytest.mark.asyncio
    async def test_run_returns_output_end_to_end(self) -> None:
        model = FunctionModel(
            lambda messages, info: ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result",
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
                        tool_name="final_result",
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
