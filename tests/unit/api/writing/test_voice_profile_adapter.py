"""Tests for backend voice profile adapter (ADR-050 P1-C)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.writing.voice_profile_adapter import make_voice_profile_consumer
from narrare_core.profiles.contracts import VoiceProfileConsumer
from narrare_core.writing.context_models import KBEntity


def _voice_entity(
    entity_id: str,
    name: str,
    *,
    updated_at: str | None = None,
    confidence: float = 1.0,
) -> KBEntity:
    return KBEntity(
        entity_id=entity_id,
        entity_type="character",
        name=name,
        content=f"{name} content.",
        updated_at=updated_at,
        confidence=confidence,
        metadata={"speech": {"dialect": "Southern"}},
    )


class TestBackendVoiceProfileAdapter:
    """Generation and checking projections share the same source."""

    def test_factory_returns_voice_profile_consumer(self) -> None:
        consumer = make_voice_profile_consumer([])
        assert isinstance(consumer, VoiceProfileConsumer)

    @pytest.mark.asyncio
    async def test_generation_and_checking_use_same_source(self) -> None:
        consumer = make_voice_profile_consumer(
            [_voice_entity("char-1", "Alice"), _voice_entity("char-2", "Bob")]
        )
        project_id = uuid4()

        generation = await consumer.assemble_for_generation(project_id)
        checking = await consumer.assemble_for_checking(project_id)

        assert {voice.name for voice in generation.character_voice_profiles} == {
            voice.name for voice in checking
        }
        assert generation.formatted_voice_profiles == "\n".join(
            f"**{voice.name}**: {voice.speech_summary}" for voice in checking
        )

    @pytest.mark.asyncio
    async def test_stale_profiles_are_labelled_not_dropped(self) -> None:
        consumer = make_voice_profile_consumer(
            [_voice_entity("char-1", "Alice", updated_at="2025-01-01T00:00:00+00:00")]
        )

        generation = await consumer.assemble_for_generation(uuid4(), max_age_days=1)
        checking = await consumer.assemble_for_checking(uuid4(), max_age_days=1)

        assert "⚠️ last updated: 2025-01-01T00:00:00+00:00" in generation.formatted_voice_profiles
        assert any("Alice" in warning for warning in generation.freshness_warnings)
        assert len(checking) == 1
        assert checking[0].is_fresh is False

    @pytest.mark.asyncio
    async def test_confidence_is_labelled_in_generation_and_checking_projection(self) -> None:
        consumer = make_voice_profile_consumer([_voice_entity("char-1", "Alice", confidence=0.42)])

        generation = await consumer.assemble_for_generation(uuid4())
        checking = await consumer.assemble_for_checking(uuid4())

        assert "confidence: 0.42" in generation.formatted_voice_profiles
        assert checking[0].speech_summary.endswith("confidence: 0.42")
