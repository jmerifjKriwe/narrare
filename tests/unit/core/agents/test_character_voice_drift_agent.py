"""Tests for CharacterVoiceDriftAgent — instantiation + RULE-02b Mode-1 loading.

Split layout (the file ends in ``_agent.py`` so check_architecture applies the
200-line agent limit — cf. the CharacterVoiceCheckerAgent test split):
- this file — instantiation + RULE-02b Mode-1 template loading
- test_character_voice_drift_process_output.py — the _process_output function
- test_character_voice_drift_agent_validation.py — ADR-035 validator invariants
- test_character_voice_drift_types.py — types + Decision-5 (no rewrite/profile)

No real LLM calls (RULE-01b).
"""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.agents.character_voice_drift_agent import (
    CharacterVoiceDriftAgent,
)


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
        sys_prompts = agent._agent._system_prompts  # type: ignore[reportPrivateUsage]
        assert resolved_template in sys_prompts

    def test_no_system_prompt_when_none(self) -> None:
        """When system_prompt is None, no static prompt is injected by the agent."""
        agent = CharacterVoiceDriftAgent(model=TestModel(), system_prompt=None)
        sys_prompts = agent._agent._system_prompts  # type: ignore[reportPrivateUsage]
        assert not sys_prompts

    def test_output_validator_registered(self) -> None:
        """ADR-035: an output validator is registered on the underlying agent."""
        agent = CharacterVoiceDriftAgent(model=TestModel())
        assert len(agent._agent._output_validators) >= 1  # type: ignore[reportPrivateUsage]

    def test_inherits_run_stream_from_base(self) -> None:
        """RULE-13 (ADR-065): the two-method run/stream interface is provided.

        ``run()`` is overridden (returns VoiceDriftResult); ``run_stream()`` is
        inherited from NarrareAgent — mirrors the sibling CharacterVoiceAgent /
        CharacterVoiceCheckerAgent.
        """
        agent = CharacterVoiceDriftAgent(model=TestModel())
        assert callable(agent.run)
        assert callable(agent.run_stream)
