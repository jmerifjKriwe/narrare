"""Character entity metadata schema with grouped fields.

Fields capture the essential attributes of a fictional character
as recommended by the bundled character template.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# Voice-generic types (VoiceMetrics + VoiceAnalysis) live in
# ``narrare_core.schemas.voice`` (ADR-074 type-reuse decision — voice-generic
# types do not belong in a character-specific file). Re-exported here for
# backward compatibility: every existing import
# (``from narrare_core.kb.schemas.character import VoiceMetrics, VoiceAnalysis``)
# and the package-level re-export in ``kb/schemas/__init__.py`` continue to
# resolve unchanged. ANAL-008 / WRITE-010 / ANAL-009-Phase-1 stay green with
# zero import edits. ONE definition (RULE-22 SSOT); these names are re-exports,
# not duplicates. ``SpeechPatterns.voice_analysis`` below also relies on the
# ``VoiceAnalysis`` re-export to keep its annotation resolvable.
from narrare_core.schemas.voice import (
    VoiceAnalysis as VoiceAnalysis,
)
from narrare_core.schemas.voice import (
    VoiceMetrics as VoiceMetrics,
)

from .base import KBEntryMetadata

__all__ = [
    "AppearanceFields",
    "BackgroundFields",
    "CharacterMetadata",
    "DevelopmentFields",
    "PersonalityFields",
    "RelationshipFields",
    "SpeechPatterns",
    "VoiceAnalysis",
    "VoiceMetrics",
]


class AppearanceFields(BaseModel):
    """Physical appearance characteristics."""

    model_config = ConfigDict(extra="allow")

    height: str | None = None
    build: str | None = None
    hair_color: str | None = None
    eye_color: str | None = None
    skin_tone: str | None = None
    distinctive_marks: str | None = None
    clothing_style: str | None = None


class PersonalityFields(BaseModel):
    """Personality traits and psychological profile."""

    model_config = ConfigDict(extra="allow")

    traits: list[str] | None = None
    strengths: list[str] | None = None
    weaknesses: list[str] | None = None
    fears: list[str] | None = None
    desires: list[str] | None = None
    motivations: str | None = None
    quirks: list[str] | None = None


class BackgroundFields(BaseModel):
    """Character background and history."""

    model_config = ConfigDict(extra="allow")

    family: str | None = None
    upbringing: str | None = None
    education: str | None = None
    key_events: list[str] | None = None
    formative_experiences: str | None = None


class SpeechPatterns(BaseModel):
    """Speech patterns and mannerisms."""

    model_config = ConfigDict(extra="allow")

    # Human-authored (unchanged):
    typical_phrases: list[str] | None = None
    dialect: str | None = None
    vocabulary_quirks: str | None = None
    body_language: str | None = None
    # Machine-derived (ANAL-008 / ADR-055):
    voice_analysis: VoiceAnalysis | None = None


class RelationshipFields(BaseModel):
    """Character relationships overview."""

    model_config = ConfigDict(extra="allow")

    allies: list[str] | None = None
    rivals: list[str] | None = None
    family_members: list[str] | None = None
    mentors: list[str] | None = None
    notes: str | None = None


class DevelopmentFields(BaseModel):
    """Character development arc."""

    model_config = ConfigDict(extra="allow")

    starting_point: str | None = None
    key_turning_points: list[str] | None = None
    current_state: str | None = None
    planned_arc: str | None = None


class CharacterMetadata(KBEntryMetadata):
    """Metadata for character KB entries with grouped fields.

    All fields are optional — the template is a recommendation, not
    enforcement.  ``extra="allow"`` is inherited from KBEntryMetadata.
    """

    # Flat fields kept for backward compat
    age: int | None = None
    role: str | None = None
    arc: str | None = None
    gender: str | None = None
    pronouns: str | None = None
    nationality: str | None = None
    pov_character: bool | None = None
    affiliation: str | None = None
    element: str | None = None
    first_appearance: str | None = None
    aliases: list[str] | None = None
    # Nested groups
    appearance: AppearanceFields | None = None
    personality: PersonalityFields | None = None
    background: BackgroundFields | None = None
    speech: SpeechPatterns | None = None
    relationships: RelationshipFields | None = None
    development: DevelopmentFields | None = None
