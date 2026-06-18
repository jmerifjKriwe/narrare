"""Backend adapter for voice profile consumers (ADR-050 P1-C).

The writing API already has KB entities in memory when it builds prompt
context. This adapter binds those entities to the Core voice-profile
contracts so generation and future checking consumers read the same
source through :class:`VoiceProfileConsumer` instead of calling the
legacy ``extract_voice_profiles`` helper directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.profiles._voice_extraction import build_character_voice_profile
from narrare_core.profiles.assembly import ProfileAssembler
from narrare_core.profiles.models import CharacterVoiceProfile

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.profiles.contracts import VoiceProfileConsumer, VoiceProfileProvider
    from narrare_core.profiles.models import ProjectWritingProfile
    from narrare_core.writing.context_models import KBEntity

logger = structlog.get_logger(__name__)


class KBEntityVoiceProfileProvider:
    """Load character voice profiles from assembled KB entities.

    Args:
        entities: KB entities already fetched for the current writing
            invocation. The provider stores a snapshot so generation and
            checking projections see the same source data.
    """

    def __init__(self, entities: list[KBEntity]) -> None:
        self._entities = tuple(entities)

    async def get_character_voices(
        self,
        project_id: UUID,
        *,
        max_age_days: int = 30,
    ) -> list[CharacterVoiceProfile]:
        """Return voice profiles extracted from character KB entities.

        Args:
            project_id: Project identifier for contract compatibility.
                The snapshot is already scoped by the caller.
            max_age_days: Freshness window for stale-profile labelling.

        Returns:
            Character voice profiles with ``is_fresh`` populated.
        """
        del project_id
        profiles: list[CharacterVoiceProfile] = []
        for entity in self._entities:
            if entity.entity_type != "character":
                continue
            profile = build_character_voice_profile(
                entity_id=entity.entity_id,
                name=entity.name,
                metadata=entity.metadata,
                updated_at=entity.updated_at,
                max_age_days=max_age_days,
            )
            if profile is None:
                continue
            if entity.confidence < 1.0:
                profile = CharacterVoiceProfile(
                    character_id=profile.character_id,
                    name=profile.name,
                    speech_summary=f"{profile.speech_summary}; confidence: {entity.confidence:.2f}",
                    updated_at=profile.updated_at,
                    is_fresh=profile.is_fresh,
                )
            if not profile.is_fresh:
                logger.warning(
                    "voice_profile_stale",
                    entity_id=entity.entity_id,
                    entity_name=entity.name,
                    updated_at=entity.updated_at,
                    max_age_days=max_age_days,
                )
            profiles.append(profile)
        return profiles


class BackendVoiceProfileConsumer:
    """VoiceProfileConsumer backed by one KB-entity provider snapshot."""

    def __init__(self, provider: VoiceProfileProvider) -> None:
        self._provider = provider
        self._assembler = ProfileAssembler(provider=provider)

    @property
    def provider(self) -> VoiceProfileProvider:
        """Return the bound provider used by every projection."""
        return self._provider

    async def assemble_for_generation(
        self,
        project_id: UUID,
        *,
        max_age_days: int = 30,
    ) -> ProjectWritingProfile:
        """Build a prompt-ready writing profile from the bound provider."""
        return await self._assembler.assemble(
            project_id=project_id,
            max_age_days=max_age_days,
        )

    async def assemble_for_checking(
        self,
        project_id: UUID,
        *,
        max_age_days: int = 30,
    ) -> list[CharacterVoiceProfile]:
        """Return structured profiles for consistency checking."""
        return await self._provider.get_character_voices(
            project_id,
            max_age_days=max_age_days,
        )


def make_voice_profile_consumer(entities: list[KBEntity]) -> VoiceProfileConsumer:
    """Create a VoiceProfileConsumer for one writing invocation.

    Args:
        entities: KB entities fetched for this generation/checking scope.

    Returns:
        Consumer whose generation and checking projections share one
        provider snapshot.
    """
    return BackendVoiceProfileConsumer(provider=KBEntityVoiceProfileProvider(entities))
