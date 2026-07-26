"""Validation tests for CharacterVoiceDriftAgent — _validate_output (ADR-035).

Tests that the output validator enforces deterministic invariants / cleanup:
- ``per_chapter_notes`` entries with an empty ``chapter_id`` are filtered.
- ``suggested_attention`` / ``longitudinal_reasons`` empty strings are filtered.
- ``confidence`` is clamped to [0.0, 1.0] defensively.
- ``drift_type`` is one of the three literals (enforced by the Pydantic Field).
- The validator never raises ModelRetry (the single-result shape is always
  present; empty lists are legitimate for a stable voice — ADR-073 D5).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.character_voice_drift_agent import (
    CharacterVoiceDriftAgent,
)
from narrare_core.agents.character_voice_drift_types import (
    ChapterNote,
    CharacterVoiceDriftDeps,
    VoiceDriftResult,
)


@pytest.fixture()
def agent() -> CharacterVoiceDriftAgent:
    return CharacterVoiceDriftAgent(model=TestModel())


def _make_ctx(
    deps: CharacterVoiceDriftDeps | None = None,
) -> RunContext[CharacterVoiceDriftDeps]:
    return RunContext[CharacterVoiceDriftDeps](
        deps=deps or CharacterVoiceDriftDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


@pytest.fixture()
def ctx() -> RunContext[CharacterVoiceDriftDeps]:
    return _make_ctx()


class TestCharacterVoiceDriftValidation:
    """_validate_output enforces deterministic cleanup invariants (ADR-035)."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(
        self,
        agent: CharacterVoiceDriftAgent,
        ctx: RunContext[CharacterVoiceDriftDeps],
    ) -> None:
        output = VoiceDriftResult(
            drift_type="inconsistency",
            confidence=0.82,
            longitudinal_reasons=["formality declines from ch-3 through ch-12"],
            per_chapter_notes=[ChapterNote(chapter_id="ch-7", note="Sharp TTR jump.")],
            suggested_attention=["ch-7"],
        )
        result = await agent._validate_output(ctx, output)
        assert result.drift_type == "inconsistency"
        assert result.confidence == 0.82
        assert len(result.longitudinal_reasons) == 1
        assert len(result.per_chapter_notes) == 1
        assert result.suggested_attention == ["ch-7"]

    @pytest.mark.asyncio
    async def test_empty_chapter_id_notes_filtered(
        self,
        agent: CharacterVoiceDriftAgent,
        ctx: RunContext[CharacterVoiceDriftDeps],
    ) -> None:
        """per_chapter_notes entries with an empty chapter_id are filtered out."""
        output = VoiceDriftResult(
            drift_type="context",
            confidence=0.6,
            per_chapter_notes=[
                ChapterNote(chapter_id="ch-7", note="Jump."),
                ChapterNote(chapter_id="", note="No anchor."),
                ChapterNote(chapter_id="  ", note="Whitespace anchor."),
            ],
        )
        validated = await agent._validate_output(ctx, output)
        assert len(validated.per_chapter_notes) == 1
        assert validated.per_chapter_notes[0].chapter_id == "ch-7"

    @pytest.mark.asyncio
    async def test_empty_suggested_attention_filtered(
        self,
        agent: CharacterVoiceDriftAgent,
        ctx: RunContext[CharacterVoiceDriftDeps],
    ) -> None:
        """Empty/whitespace suggested_attention entries are filtered out."""
        output = VoiceDriftResult(
            drift_type="inconsistency",
            confidence=0.7,
            suggested_attention=["ch-7", "", "  ", "ch-11"],
        )
        validated = await agent._validate_output(ctx, output)
        assert validated.suggested_attention == ["ch-7", "ch-11"]

    @pytest.mark.asyncio
    async def test_empty_longitudinal_reasons_filtered(
        self,
        agent: CharacterVoiceDriftAgent,
        ctx: RunContext[CharacterVoiceDriftDeps],
    ) -> None:
        """Empty/whitespace longitudinal_reasons entries are filtered out."""
        output = VoiceDriftResult(
            drift_type="evolution",
            confidence=0.8,
            longitudinal_reasons=["formality rises across the arc", "", "  "],
        )
        validated = await agent._validate_output(ctx, output)
        assert validated.longitudinal_reasons == ["formality rises across the arc"]

    @pytest.mark.asyncio
    async def test_confidence_bounds_enforced_by_field_not_validator(
        self,
        agent: CharacterVoiceDriftAgent,
        ctx: RunContext[CharacterVoiceDriftDeps],
    ) -> None:
        """confidence bounds are enforced by the Pydantic Field (ADR-035).

        Out-of-range values raise ``ValidationError`` at construction (before
        the validator runs) — mirroring the checker's ``qualitative_sub_score``.
        The validator therefore does not clamp; the Field is the bounds gate.
        """
        with pytest.raises(ValidationError):
            VoiceDriftResult(confidence=1.0000001)
        with pytest.raises(ValidationError):
            VoiceDriftResult(confidence=-0.0000001)
        # In-range values pass through the validator unchanged.
        validated = await agent._validate_output(ctx, VoiceDriftResult(confidence=0.5))
        assert validated.confidence == 0.5

    @pytest.mark.asyncio
    async def test_empty_lists_are_valid_no_retry(
        self,
        agent: CharacterVoiceDriftAgent,
        ctx: RunContext[CharacterVoiceDriftDeps],
    ) -> None:
        """Empty per_chapter_notes + suggested_attention is valid (stable voice).

        ADR-073 Decision 5: a stable voice legitimately yields empty lists —
        the validator must NOT raise ModelRetry (unlike the checker, which
        requires at least one named entry).
        """
        output = VoiceDriftResult(
            drift_type="evolution",
            confidence=0.9,
            longitudinal_reasons=["trend is flat and high-scoring"],
            per_chapter_notes=[],
            suggested_attention=[],
        )
        result = await agent._validate_output(ctx, output)
        assert result.per_chapter_notes == []
        assert result.suggested_attention == []

    @pytest.mark.asyncio
    async def test_empty_trend_convention_is_valid(
        self,
        agent: CharacterVoiceDriftAgent,
        ctx: RunContext[CharacterVoiceDriftDeps],
    ) -> None:
        """The template's empty-trend convention (confidence=0.0) is valid."""
        output = VoiceDriftResult(
            drift_type="evolution",
            confidence=0.0,
            longitudinal_reasons=[],
            per_chapter_notes=[],
            suggested_attention=[],
        )
        result = await agent._validate_output(ctx, output)
        assert result.confidence == 0.0


class TestDriftTypeEnforcedByField:
    """drift_type is bounded to the three literals by the Pydantic Field."""

    def test_invalid_drift_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VoiceDriftResult(
                drift_type="stable",  # type: ignore[arg-type]
            )

    def test_all_three_valid(self) -> None:
        for dt in ("evolution", "context", "inconsistency"):
            result = VoiceDriftResult(drift_type=dt)  # type: ignore[arg-type]
            assert result.drift_type == dt
