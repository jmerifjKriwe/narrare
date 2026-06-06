"""Profile data models — immutable, in-memory data classes for P2.

These dataclasses represent writing profile data at invocation time.
No storage, no I/O — pure value objects.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CharacterVoiceProfile:
    """Voice profile for a single character entity."""

    character_id: str
    name: str
    speech_summary: str  # Formatted speech/personality text
    updated_at: str | None = None
    is_fresh: bool = True


@dataclass(frozen=True)
class ProjectWritingProfile:
    """Consolidated writing profile for a project.

    In-memory only in P2.  Assembled at invocation time from KB entities
    and project settings.
    """

    writing_language: str = "en"
    genre: str | None = None
    tone: str | None = None
    style_profile: str | None = None
    character_voice_profiles: tuple[CharacterVoiceProfile, ...] = ()
    freshness_warnings: tuple[str, ...] = ()

    @property
    def has_voice_profiles(self) -> bool:
        """Whether any character voice profiles are present."""
        return len(self.character_voice_profiles) > 0

    @property
    def formatted_voice_profiles(self) -> str:
        """Format voice profiles as text block for prompt injection."""
        if not self.character_voice_profiles:
            return ""
        parts: list[str] = []
        for vp in self.character_voice_profiles:
            line = f"**{vp.name}**: {vp.speech_summary}"
            if not vp.is_fresh and vp.updated_at:
                line += f" [\u26a0\ufe0f last updated: {vp.updated_at}]"
            parts.append(line)
        return "\n".join(parts)
