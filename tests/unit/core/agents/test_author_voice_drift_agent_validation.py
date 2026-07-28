"""Validation tests for AuthorVoiceDriftAgent — _validate_output (ADR-035).

Mirrors ``test_character_voice_drift_agent_validation.py``. The author drift
agent REUSES :class:`VoiceDriftResult`, so the validator enforces the SAME
deterministic invariants / cleanup:
- ``per_chapter_notes`` entries with an empty ``chapter_id`` are filtered.
- ``suggested_attention`` / ``longitudinal_reasons`` empty strings are filtered.
- ``confidence`` bounds (0.0-1.0) are enforced by the Pydantic Field.
- ``drift_type`` is one of the three literals (enforced by the Pydantic Field).
- The validator never raises ModelRetry (single-result shape is always present;
  empty lists are legitimate for a stable narrator voice).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.author_voice_drift_agent import AuthorVoiceDriftAgent
from narrare_core.agents.author_voice_drift_types import AuthorVoiceDriftDeps
from narrare_core.agents.character_voice_drift_types import (
    ChapterNote,
    VoiceDriftResult,
)


@pytest.fixture()
def agent() -> AuthorVoiceDriftAgent:
    return AuthorVoiceDriftAgent(model=TestModel())


def _make_ctx(
    deps: AuthorVoiceDriftDeps | None = None,
) -> RunContext[AuthorVoiceDriftDeps]:
    return RunContext[AuthorVoiceDriftDeps](
        deps=deps or AuthorVoiceDriftDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


@pytest.fixture()
def ctx() -> RunContext[AuthorVoiceDriftDeps]:
    return _make_ctx()


class TestAuthorVoiceDriftValidation:
    """_validate_output enforces deterministic cleanup invariants (ADR-035)."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(
        self,
        agent: AuthorVoiceDriftAgent,
        ctx: RunContext[AuthorVoiceDriftDeps],
    ) -> None:
        output = VoiceDriftResult(
            drift_type="inconsistency",
            confidence=0.82,
            longitudinal_reasons=["dialogue_ratio rises sharply from ch-3"],
            per_chapter_notes=[ChapterNote(chapter_id="ch-7", note="Density jump.")],
            suggested_attention=["ch-7"],
        )
        result = await agent._validate_output(ctx, output)
        assert result.drift_type == "inconsistency"
        assert result.confidence == 0.82
        assert len(result.longitudinal_reasons) == 1
        assert result.suggested_attention == ["ch-7"]

    @pytest.mark.asyncio
    async def test_empty_chapter_id_notes_filtered(
        self,
        agent: AuthorVoiceDriftAgent,
        ctx: RunContext[AuthorVoiceDriftDeps],
    ) -> None:
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
        agent: AuthorVoiceDriftAgent,
        ctx: RunContext[AuthorVoiceDriftDeps],
    ) -> None:
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
        agent: AuthorVoiceDriftAgent,
        ctx: RunContext[AuthorVoiceDriftDeps],
    ) -> None:
        output = VoiceDriftResult(
            drift_type="evolution",
            confidence=0.8,
            longitudinal_reasons=["description density rises across the arc", "", "  "],
        )
        validated = await agent._validate_output(ctx, output)
        assert validated.longitudinal_reasons == ["description density rises across the arc"]

    @pytest.mark.asyncio
    async def test_confidence_bounds_enforced_by_field_not_validator(
        self,
        agent: AuthorVoiceDriftAgent,
        ctx: RunContext[AuthorVoiceDriftDeps],
    ) -> None:
        with pytest.raises(ValidationError):
            VoiceDriftResult(confidence=1.0000001)
        with pytest.raises(ValidationError):
            VoiceDriftResult(confidence=-0.0000001)
        validated = await agent._validate_output(ctx, VoiceDriftResult(confidence=0.5))
        assert validated.confidence == 0.5

    @pytest.mark.asyncio
    async def test_empty_lists_are_valid_no_retry(
        self,
        agent: AuthorVoiceDriftAgent,
        ctx: RunContext[AuthorVoiceDriftDeps],
    ) -> None:
        """A stable narrator voice legitimately yields empty lists."""
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
        agent: AuthorVoiceDriftAgent,
        ctx: RunContext[AuthorVoiceDriftDeps],
    ) -> None:
        output = VoiceDriftResult(
            drift_type="evolution",
            confidence=0.0,
            longitudinal_reasons=[],
            per_chapter_notes=[],
            suggested_attention=[],
        )
        result = await agent._validate_output(ctx, output)
        assert result.confidence == 0.0
