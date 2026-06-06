"""Project writing profiles — SSOT for voice, language, genre, tone, style.

Consolidates character voice profiles, writing language, genre, tone,
and style preferences previously scattered across the writing subsystem.

This module has ZERO imports from ``writing/`` (RULE-07).
"""

from narrare_core.profiles.assembly import ProfileAssembler
from narrare_core.profiles.contracts import VoiceProfileProvider
from narrare_core.profiles.models import CharacterVoiceProfile, ProjectWritingProfile

__all__ = [
    "CharacterVoiceProfile",
    "ProfileAssembler",
    "ProjectWritingProfile",
    "VoiceProfileProvider",
]
