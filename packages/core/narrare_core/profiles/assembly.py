"""Profile assembly — assembles ProjectWritingProfile from providers.

In-memory only in P2 — no storage.  Uses injected VoiceProfileProvider
for character voice data (RULE-03: contract before implementation).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.profiles.models import ProjectWritingProfile

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.profiles.contracts import VoiceProfileProvider
    from narrare_core.profiles.models import CharacterVoiceProfile

logger = structlog.get_logger(__name__)


class ProfileAssembler:
    """Assembles :class:`ProjectWritingProfile` from voice provider + settings.

    In-memory only in P2 — no storage.

    Usage::

        provider = MyVoiceProvider(...)
        assembler = ProfileAssembler(provider=provider)
        profile = await assembler.assemble(
            project_id=project_id,
            writing_language="en",
            genre="fantasy",
        )
    """

    def __init__(self, provider: VoiceProfileProvider | None = None) -> None:
        self._provider = provider

    @property
    def provider(self) -> VoiceProfileProvider:
        """Return the bound voice profile provider.

        Raises:
            RuntimeError: If no provider is configured. A provider-less
                assembler can still build a minimal profile, but it does
                not satisfy the consumer binding requirement at runtime.
        """
        if self._provider is None:
            raise RuntimeError("VoiceProfileProvider is not configured")
        return self._provider

    async def assemble(
        self,
        project_id: UUID,
        *,
        writing_language: str = "en",
        genre: str | None = None,
        tone: str | None = None,
        style_profile: str | None = None,
        max_age_days: int = 30,
    ) -> ProjectWritingProfile:
        """Assemble the project writing profile from available sources.

        If no provider is configured, returns a minimal profile with
        only the provided settings (no voice profiles).
        """
        if self._provider is None:
            return ProjectWritingProfile(
                writing_language=writing_language,
                genre=genre,
                tone=tone,
                style_profile=style_profile,
            )

        voices = await self._provider.get_character_voices(
            project_id,
            max_age_days=max_age_days,
        )

        freshness_warnings: list[str] = []
        for vp in voices:
            if not vp.is_fresh and vp.updated_at:
                freshness_warnings.append(
                    f"Voice profile for '{vp.name}' last updated {vp.updated_at} "
                    f"(>{max_age_days} days ago)"
                )

        return ProjectWritingProfile(
            writing_language=writing_language,
            genre=genre,
            tone=tone,
            style_profile=style_profile,
            character_voice_profiles=tuple(voices),
            freshness_warnings=tuple(freshness_warnings),
        )

    async def assemble_for_generation(
        self,
        project_id: UUID,
        *,
        max_age_days: int = 30,
    ) -> ProjectWritingProfile:
        """Assemble the generation projection for VoiceProfileConsumer."""
        return await self.assemble(project_id=project_id, max_age_days=max_age_days)

    async def assemble_for_checking(
        self,
        project_id: UUID,
        *,
        max_age_days: int = 30,
    ) -> list[CharacterVoiceProfile]:
        """Return structured voice profiles for checking consumers."""
        if self._provider is None:
            return []
        return await self._provider.get_character_voices(
            project_id,
            max_age_days=max_age_days,
        )
