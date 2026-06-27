"""Character entity metadata schema with grouped fields.

Fields capture the essential attributes of a fictional character
as recommended by the bundled character template.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .base import KBEntryMetadata


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


class VoiceMetrics(BaseModel):
    """Deterministic numeric metrics — for ANAL-009 drift / WRITE-010 checking.

    NOT rendered into generation. Populated by the deterministic
    ``VoiceMetricsAnalyzer`` (ADR-021/ADR-055), never by the LLM agent.
    ``extra="allow"`` lets the metric block grow without a migration.
    """

    model_config = ConfigDict(extra="allow")

    avg_sentence_length: float | None = None
    sentence_length_std: float | None = None
    type_token_ratio: float | None = None
    avg_syllables_per_word: float | None = None
    contraction_rate: float | None = None
    verbal_tic_frequency: dict[str, float] | None = None  # n-gram -> rate
    punctuation_profile: dict[str, float] | None = None  # habit -> rate


class VoiceAnalysis(BaseModel):
    """Machine-derived character voice profile (ADR-055 Decision 1).

    ANAL-008 writes this; the extended ``get_speech_data`` consumer renders
    the descriptive group into ``{{character_voice_profiles}}``. The metric
    group is comparison-only and NEVER reaches generation.
    """

    model_config = ConfigDict(extra="allow")

    # Descriptive group (rendered into generation by the extended consumer)
    formality: float | None = None  # 0.0 casual - 1.0 formal
    vocabulary_level: str | None = None  # simple | moderate | complex
    sentence_profile: str | None = None  # short | medium | long | varied
    emotional_range: str | None = None  # restricted | moderate | expressive
    cultural_regional_markers: str | None = None  # intrinsic markers aiding generation
    voice_examples: list[str] | None = None  # curated representative quotes

    # Metric group (comparison ONLY — never rendered into generation)
    voice_metrics: VoiceMetrics | None = None


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
