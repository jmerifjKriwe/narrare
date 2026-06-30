"""Validation tests for CharacterVoiceCheckerAgent — _validate_output (ADR-035).

Split from test_character_voice_checker_agent.py to mirror the
CharacterVoiceAgent test layout. Tests that the output validator enforces
deterministic invariants:
- At least one character entry with a non-empty name.
- Empty-name entries are filtered.
- ``qualitative_sub_score`` bounds (0.0-100.0) are enforced by the Pydantic Field.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.character_voice_checker_agent import (
    CharacterVoiceCheckerAgent,
)
from narrare_core.agents.character_voice_checker_types import (
    CharacterVoiceCheckerDeps,
    CharacterVoiceCheckerEntry,
    CharacterVoiceCheckerOutput,
    FlaggedLine,
)


@pytest.fixture()
def agent() -> CharacterVoiceCheckerAgent:
    return CharacterVoiceCheckerAgent(model=TestModel())


def _make_ctx(
    deps: CharacterVoiceCheckerDeps | None = None,
) -> RunContext[CharacterVoiceCheckerDeps]:
    return RunContext[CharacterVoiceCheckerDeps](
        deps=deps or CharacterVoiceCheckerDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


@pytest.fixture()
def ctx() -> RunContext[CharacterVoiceCheckerDeps]:
    return _make_ctx()


class TestCharacterVoiceCheckerValidation:
    """_validate_output enforces deterministic invariants (ADR-035)."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(
        self,
        agent: CharacterVoiceCheckerAgent,
        ctx: RunContext[CharacterVoiceCheckerDeps],
    ) -> None:
        output = CharacterVoiceCheckerOutput(
            characters=[
                CharacterVoiceCheckerEntry(
                    character_name="Elena",
                    match_judgment="consistent",
                    qualitative_sub_score=92.0,
                ),
            ],
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.characters) == 1
        assert result.characters[0].qualitative_sub_score == 92.0

    @pytest.mark.asyncio
    async def test_empty_characters_triggers_model_retry(
        self,
        agent: CharacterVoiceCheckerAgent,
        ctx: RunContext[CharacterVoiceCheckerDeps],
    ) -> None:
        """An empty characters list raises ModelRetry."""
        with pytest.raises(ModelRetry):
            await agent._validate_output(ctx, CharacterVoiceCheckerOutput(characters=[]))

    @pytest.mark.asyncio
    async def test_empty_character_name_filtered(
        self,
        agent: CharacterVoiceCheckerAgent,
        ctx: RunContext[CharacterVoiceCheckerDeps],
    ) -> None:
        """Entries with an empty character_name are filtered out."""
        output = CharacterVoiceCheckerOutput(
            characters=[
                CharacterVoiceCheckerEntry(character_name="Elena"),
                CharacterVoiceCheckerEntry(character_name=""),
                CharacterVoiceCheckerEntry(character_name="  "),
            ],
        )
        validated = await agent._validate_output(ctx, output)
        assert len(validated.characters) == 1
        assert validated.characters[0].character_name == "Elena"

    @pytest.mark.asyncio
    async def test_all_empty_names_triggers_model_retry(
        self,
        agent: CharacterVoiceCheckerAgent,
        ctx: RunContext[CharacterVoiceCheckerDeps],
    ) -> None:
        """If all entries have empty names, ModelRetry is raised."""
        output = CharacterVoiceCheckerOutput(
            characters=[
                CharacterVoiceCheckerEntry(character_name=""),
                CharacterVoiceCheckerEntry(character_name="  "),
            ],
        )
        with pytest.raises(ModelRetry):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_flagged_lines_preserved_in_output(
        self,
        agent: CharacterVoiceCheckerAgent,
        ctx: RunContext[CharacterVoiceCheckerDeps],
    ) -> None:
        """flagged_lines pass through validation unchanged (flag+score scope)."""
        output = CharacterVoiceCheckerOutput(
            characters=[
                CharacterVoiceCheckerEntry(
                    character_name="Marc",
                    match_judgment="notable_drift",
                    qualitative_sub_score=55.0,
                    flagged_lines=[
                        FlaggedLine(
                            quote="Aye.",
                            reason="Omits the stored verbal tic.",
                        )
                    ],
                ),
            ],
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.characters[0].flagged_lines) == 1
        assert result.characters[0].flagged_lines[0].quote == "Aye."

    @pytest.mark.asyncio
    async def test_no_dialogue_convention_passes(
        self,
        agent: CharacterVoiceCheckerAgent,
        ctx: RunContext[CharacterVoiceCheckerDeps],
    ) -> None:
        """The template's "no dialogue" convention is a valid output.

        A character with no attributable dialogue yields an empty flagged_lines
        list, ``consistent`` judgment, and ``100.0`` sub-score — valid, not a
        retry.
        """
        output = CharacterVoiceCheckerOutput(
            characters=[
                CharacterVoiceCheckerEntry(
                    character_name="Elena",
                    match_judgment="consistent",
                    qualitative_sub_score=100.0,
                    flagged_lines=[],
                ),
            ],
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.characters) == 1


class TestQualitativeSubScoreBounds:
    """qualitative_sub_score is bounded to [0.0, 100.0] by the Pydantic Field."""

    def test_zero_is_valid(self) -> None:
        entry = CharacterVoiceCheckerEntry(character_name="Elena", qualitative_sub_score=0.0)
        assert entry.qualitative_sub_score == 0.0

    def test_one_hundred_is_valid(self) -> None:
        entry = CharacterVoiceCheckerEntry(character_name="Elena", qualitative_sub_score=100.0)
        assert entry.qualitative_sub_score == 100.0

    def test_above_100_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CharacterVoiceCheckerEntry(character_name="Elena", qualitative_sub_score=100.1)

    def test_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CharacterVoiceCheckerEntry(character_name="Elena", qualitative_sub_score=-0.1)

    def test_default_is_100(self) -> None:
        entry = CharacterVoiceCheckerEntry(character_name="Elena")
        assert entry.qualitative_sub_score == 100.0
