"""Profile contracts — Protocols for profile assembly dependencies.

RULE-03: Contract before implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from narrare_core.profiles.models import CharacterVoiceProfile


class VoiceProfileProvider(Protocol):
    """Provides character voice data for profile assembly."""

    async def get_character_voices(
        self,
        project_id: object,
    ) -> list[CharacterVoiceProfile]:
        """Load character voice profiles for a project."""
        ...
