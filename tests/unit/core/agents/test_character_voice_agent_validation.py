"""Validation tests for CharacterVoiceAgent — _validate_output invariants (ADR-035).

Split from test_character_voice_agent.py to respect the RULE-04 200-line test
file limit. Tests that the output validator enforces deterministic invariants:
- At least one character entry with a non-empty name.
- Empty-name entries are filtered.
- distinctiveness_notes is preserved on the agent output (excluded only by merge).
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.character_voice_agent import CharacterVoiceAgent
from narrare_core.agents.character_voice_types import (
    CharacterVoiceDeps,
    CharacterVoiceEntry,
    CharacterVoiceOutput,
)


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


class TestCharacterVoiceAgentValidation:
    """_validate_output enforces deterministic invariants (ADR-035)."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(
        self, agent: CharacterVoiceAgent, ctx: RunContext[CharacterVoiceDeps]
    ) -> None:
        output = CharacterVoiceOutput(
            characters=[
                CharacterVoiceEntry(character_name="Elena", formality=0.7),
            ],
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.characters) == 1

    @pytest.mark.asyncio
    async def test_empty_characters_triggers_model_retry(
        self, agent: CharacterVoiceAgent, ctx: RunContext[CharacterVoiceDeps]
    ) -> None:
        """An empty characters list raises ModelRetry."""
        with pytest.raises(ModelRetry):
            await agent._validate_output(ctx, CharacterVoiceOutput(characters=[]))

    @pytest.mark.asyncio
    async def test_empty_character_name_filtered(
        self, agent: CharacterVoiceAgent, ctx: RunContext[CharacterVoiceDeps]
    ) -> None:
        """Entries with an empty character_name are filtered out."""
        output = CharacterVoiceOutput(
            characters=[
                CharacterVoiceEntry(character_name="Elena", formality=0.7),
                CharacterVoiceEntry(character_name="", formality=0.5),
                CharacterVoiceEntry(character_name="  ", formality=0.5),
            ],
        )
        validated = await agent._validate_output(ctx, output)
        assert len(validated.characters) == 1
        assert validated.characters[0].character_name == "Elena"

    @pytest.mark.asyncio
    async def test_all_empty_names_triggers_model_retry(
        self, agent: CharacterVoiceAgent, ctx: RunContext[CharacterVoiceDeps]
    ) -> None:
        """If all entries have empty names, ModelRetry is raised."""
        output = CharacterVoiceOutput(
            characters=[
                CharacterVoiceEntry(character_name=""),
                CharacterVoiceEntry(character_name="  "),
            ],
        )
        with pytest.raises(ModelRetry):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_empty_voice_examples_with_name_passes(
        self, agent: CharacterVoiceAgent, ctx: RunContext[CharacterVoiceDeps]
    ) -> None:
        """An entry with empty voice_examples but a valid name is valid.

        The template says: if a character has no attributable dialogue, still
        return a profile with empty voice_examples.
        """
        output = CharacterVoiceOutput(
            characters=[
                CharacterVoiceEntry(
                    character_name="Elena",
                    voice_examples=[],
                    distinctiveness_notes="Insufficient data.",
                ),
            ],
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.characters) == 1
        assert result.characters[0].voice_examples == []

    @pytest.mark.asyncio
    async def test_distinctiveness_notes_preserved_in_output(
        self, agent: CharacterVoiceAgent, ctx: RunContext[CharacterVoiceDeps]
    ) -> None:
        """distinctiveness_notes is preserved on the agent output (NOT persisted by merge)."""
        output = CharacterVoiceOutput(
            characters=[
                CharacterVoiceEntry(
                    character_name="Elena",
                    distinctiveness_notes="More formal than Marc.",
                ),
            ],
        )
        result = await agent._validate_output(ctx, output)
        assert result.characters[0].distinctiveness_notes == "More formal than Marc."
