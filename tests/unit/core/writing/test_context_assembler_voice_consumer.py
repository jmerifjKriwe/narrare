"""WritingContextAssembler voice consumer wiring tests (ADR-050 P1-C)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from narrare_core.profiles.models import CharacterVoiceProfile, ProjectWritingProfile
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.context_models import KBEntity

if TYPE_CHECKING:
    from narrare_core.profiles.contracts import VoiceProfileProvider


class FakeVoiceConsumer:
    """Fake VoiceProfileConsumer that records generation calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[UUID, int]] = []

    @property
    def provider(self) -> VoiceProfileProvider:
        raise AssertionError("provider should not be needed by the assembler")

    async def assemble_for_generation(
        self,
        project_id: UUID,
        *,
        max_age_days: int = 30,
    ) -> ProjectWritingProfile:
        self.calls.append((project_id, max_age_days))
        voice = CharacterVoiceProfile(
            character_id="char-1",
            name="Alice",
            speech_summary="dialect: Southern",
            updated_at="2026-06-01",
            is_fresh=True,
        )
        return ProjectWritingProfile(
            character_voice_profiles=(voice,),
            freshness_warnings=("freshness label retained",),
        )

    async def assemble_for_checking(
        self,
        project_id: UUID,
        *,
        max_age_days: int = 30,
    ) -> list[CharacterVoiceProfile]:
        raise AssertionError("checking projection is not used during generation assembly")


@pytest.mark.asyncio
async def test_assembler_uses_voice_profile_consumer_generation_projection() -> None:
    assembler = WritingContextAssembler(total_budget=6000)
    consumer = FakeVoiceConsumer()
    project_id = uuid4()

    context = await assembler.assemble(
        project_id=project_id,
        voice_profile_consumer=consumer,
        kb_entities=[
            KBEntity(
                entity_id="char-1",
                entity_type="character",
                name="Alice",
                content="A warrior.",
                metadata={"speech": {"dialect": "Southern"}},
            )
        ],
    )

    assert consumer.calls == [(project_id, 30)]
    assert context.character_voice_profiles == "**Alice**: dialect: Southern"
    assert context.voice_profile_warnings == ["freshness label retained"]


@pytest.mark.asyncio
async def test_assembler_does_not_use_direct_extract_fallback() -> None:
    assembler = WritingContextAssembler(total_budget=6000)

    context = await assembler.assemble(
        project_id=uuid4(),
        kb_entities=[
            KBEntity(
                entity_id="char-1",
                entity_type="character",
                name="Alice",
                content="A warrior.",
                metadata={"speech": {"dialect": "Southern"}},
            )
        ],
    )

    assert context.character_voice_profiles == ""
    assert context.voice_profile_warnings == []
