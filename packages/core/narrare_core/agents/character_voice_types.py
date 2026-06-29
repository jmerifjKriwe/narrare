"""Output + dependency types for CharacterVoiceAgent (ANAL-008 / ADR-055).

Mirrors the governed ``character_voice`` template's JSON contract: a wrapper
with a ``characters`` list, each entry carrying the qualitative fields the
agent derives by interpreting the deterministic
:class:`~narrare_core.kb.schemas.character.VoiceMetrics`.

``distinctiveness_notes`` is a **per-run comparison artifact** — it is
relative to whichever other characters were analysed in the same invocation
and is NOT an intrinsic property of the character. It is therefore present
on the agent output (surfaced to the UI as a review aid) but explicitly
dropped by :func:`~narrare_core.agents.character_voice_merge.merge_character_voice`
when persisting a :class:`~narrare_core.kb.schemas.character.VoiceAnalysis`
(ADR-055 Decision 1 persistence scope).

See:
    ADR-055 — Character voice storage contract (Decisions 1, 2, 3).
    ADR-035 — Agent output validation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Enumerations from the governed template's output contract.
VocabularyLevel = Literal["simple", "moderate", "complex"]
SentenceProfile = Literal["short", "medium", "long", "varied"]
EmotionalRange = Literal["restricted", "moderate", "expressive"]


class CharacterVoiceEntry(BaseModel):
    """Qualitative voice profile for a single character (one LLM judgement).

    Attributes:
        character_name: The character's canonical name.
        formality: Formality register ``0.0`` (informal/colloquial) - ``1.0``
            (formal/elevated).
        vocabulary_level: ``"simple"`` | ``"moderate"`` | ``"complex"``.
        sentence_profile: ``"short"`` | ``"medium"`` | ``"long"`` | ``"varied"``.
        emotional_range: ``"restricted"`` | ``"moderate"`` | ``"expressive"``.
        cultural_regional_markers: Intrinsic markers (dialect, idiom, register
            cues) that aid generation, or ``None`` when none are evident.
        voice_examples: 2-4 short verbatim quotes exemplifying the voice.
        distinctiveness_notes: Relative, per-run comparison vs the *other*
            characters analysed in the same invocation. NOT persisted on the
            character profile (ADR-055 Decision 1).
    """

    character_name: str = ""
    formality: float = Field(default=0.5, ge=0.0, le=1.0)
    vocabulary_level: VocabularyLevel = "moderate"
    sentence_profile: SentenceProfile = "medium"
    emotional_range: EmotionalRange = "moderate"
    cultural_regional_markers: str | None = None
    voice_examples: list[str] = Field(default_factory=list)
    distinctiveness_notes: str | None = None


class CharacterVoiceOutput(BaseModel):
    """Structured output wrapper from CharacterVoiceAgent.

    A single LLM call profiles all supplied characters, so the contract is a
    wrapper with a ``characters`` list — exactly the template's JSON shape.
    """

    characters: list[CharacterVoiceEntry] = []


class CharacterVoiceDeps:
    """Dependencies for CharacterVoiceAgent.

    A plain class (not Pydantic) — follows the established ``CoreferenceDeps``,
    ``POVDeps``, ``ReadabilityDeps`` pattern. The governed ``character_voice``
    template is the system prompt (resolved Mode 1 by the Layer-3 service and
    passed to the agent constructor, RULE-02b). The dialogue + per-character
    metrics flow as runtime content in the agent run prompt (user channel,
    RULE-02a category 3); the same data is carried here for structured access.

    Attributes:
        attributed_dialogue: Speaker-tagged dialogue text (runtime content).
        voice_metrics_summary: Per-character deterministic metrics, formatted
            for the model (runtime content).
        character_names: The characters to profile in this run.
        project_title: Project title (prompt context).
        genre: Project genre (prompt context).
        writing_language: Language code (``"en"``, ``"de"``, ``"fr"``).
        chapter_title: Chapter title (prompt context).
    """

    def __init__(
        self,
        *,
        attributed_dialogue: str = "",
        voice_metrics_summary: str = "",
        character_names: list[str] | None = None,
        project_title: str = "",
        genre: str = "",
        writing_language: str = "en",
        chapter_title: str = "",
    ) -> None:
        self.attributed_dialogue = attributed_dialogue
        self.voice_metrics_summary = voice_metrics_summary
        self.character_names = list(character_names) if character_names else []
        self.project_title = project_title
        self.genre = genre
        self.writing_language = writing_language
        self.chapter_title = chapter_title
