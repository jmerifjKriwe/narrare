"""Tests for CharacterVoiceAgent — instantiation and deps wiring.

The strict output validator (ADR-035) is tested separately in
test_character_voice_agent_validation.py. No real LLM calls (RULE-01b).
Type/deps tests live in test_character_voice_types.py.
"""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.agents.character_voice_agent import CharacterVoiceAgent

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> CharacterVoiceAgent:
    return CharacterVoiceAgent(model=TestModel())


# ---------------------------------------------------------------------------
# C. Instantiation
# ---------------------------------------------------------------------------


class TestCharacterVoiceAgentInstantiation:
    """CharacterVoiceAgent instantiates correctly."""

    def test_can_be_instantiated(self) -> None:
        agent = CharacterVoiceAgent(model=TestModel())
        assert isinstance(agent, CharacterVoiceAgent)

    def test_instantiated_with_system_prompt(self) -> None:
        """The governed character_voice template is passed as system_prompt (Mode 1)."""
        agent = CharacterVoiceAgent(
            model=TestModel(),
            system_prompt="You are a character-voice profiling specialist.",
        )
        assert isinstance(agent, CharacterVoiceAgent)

    def test_instantiated_without_system_prompt(self) -> None:
        """Agent can be instantiated without a system_prompt (tests, fallback)."""
        agent = CharacterVoiceAgent(model=TestModel(), system_prompt=None)
        assert isinstance(agent, CharacterVoiceAgent)
