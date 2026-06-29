"""Tests for CharacterVoiceAgent — instantiation, output function, and validation.

The agent's strict output validator (ADR-035) rejects TestModel's random
default output, so — following the CoreferenceAgent / ReadabilityAgent test
pattern — the output function is tested directly and the validator is tested
separately. No real LLM calls (RULE-01b). Type/deps tests live in
test_character_voice_types.py.
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.character_voice_agent import CharacterVoiceAgent
from narrare_core.agents.character_voice_types import (
    CharacterVoiceDeps,
    CharacterVoiceOutput,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> CharacterVoiceAgent:
    return CharacterVoiceAgent(model=TestModel())


def _make_ctx(deps: CharacterVoiceDeps | None = None) -> RunContext[CharacterVoiceDeps]:
    return RunContext[CharacterVoiceDeps](
        deps=deps or CharacterVoiceDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


@pytest.fixture()
def ctx() -> RunContext[CharacterVoiceDeps]:
    return _make_ctx()


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


# ---------------------------------------------------------------------------
# D. Output function (_process_output)
#
# TestModel's random default output triggers the strict validator, so the
# output function is tested directly with valid args — CoreferenceAgent
# pattern (test_coreference_agent.py).
# ---------------------------------------------------------------------------


class TestCharacterVoiceAgentProcessOutput:
    """The _process_output output function structures the LLM response."""

    @pytest.mark.asyncio
    async def test_process_output_returns_output(self) -> None:
        agent = CharacterVoiceAgent(model=TestModel())
        ctx = _make_ctx(
            CharacterVoiceDeps(
                attributed_dialogue='Elena: "Hello there."',
                character_names=["Elena"],
                writing_language="en",
            )
        )
        result = await agent._process_output(  # type: ignore[reportPrivateUsage]
            ctx,
            characters=[
                {
                    "character_name": "Elena",
                    "formality": 0.7,
                    "vocabulary_level": "complex",
                    "sentence_profile": "varied",
                    "emotional_range": "expressive",
                    "cultural_regional_markers": "formal register",
                    "voice_examples": ["Hello there."],
                    "distinctiveness_notes": "More formal than Marc.",
                }
            ],
        )
        assert isinstance(result, CharacterVoiceOutput)
        assert len(result.characters) == 1
        assert result.characters[0].character_name == "Elena"
        assert result.characters[0].formality == 0.7
        assert result.characters[0].vocabulary_level == "complex"

    @pytest.mark.asyncio
    async def test_process_output_with_defaults(self) -> None:
        """No arguments produce a valid empty CharacterVoiceOutput."""
        agent = CharacterVoiceAgent(model=TestModel())
        result = await agent._process_output(_make_ctx())
        assert isinstance(result, CharacterVoiceOutput)
        assert result.characters == []

    @pytest.mark.asyncio
    async def test_process_output_multiple_characters(self) -> None:
        """A single LLM call profiles all supplied characters."""
        agent = CharacterVoiceAgent(model=TestModel())
        result = await agent._process_output(
            _make_ctx(),
            characters=[
                {"character_name": "Elena", "formality": 0.8},
                {"character_name": "Marc", "formality": 0.3},
            ],
        )
        assert len(result.characters) == 2
        assert result.characters[0].character_name == "Elena"
        assert result.characters[1].character_name == "Marc"

    @pytest.mark.asyncio
    async def test_process_output_with_german_language(self) -> None:
        agent = CharacterVoiceAgent(model=TestModel())
        ctx = _make_ctx(
            CharacterVoiceDeps(
                attributed_dialogue='Elena: "Hallo."',
                writing_language="de",
            )
        )
        result = await agent._process_output(
            ctx,
            characters=[{"character_name": "Elena", "voice_examples": ["Hallo."]}],
        )
        assert isinstance(result, CharacterVoiceOutput)
        assert result.characters[0].voice_examples == ["Hallo."]
