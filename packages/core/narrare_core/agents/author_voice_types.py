"""Output + dependency types for AuthorVoiceAgent (ANAL-007 / ADR-074).

Mirrors the governed ``author_voice`` template's JSON contract: a flat
structured object carrying the descriptive fields the agent derives by
interpreting the chapter prose together with the deterministic
:class:`~narrare_core.schemas.voice.VoiceMetrics` +
:class:`~narrare_core.analysis.author_metrics.AuthorMetrics`.

Binding boundary (ADR-074 — binding): this output type carries the
DESCRIPTIVE group ONLY. It NEVER carries ``VoiceMetrics`` or ``AuthorMetrics``
— measurement is deterministic, done by the analyzers (preserves ADR-021 +
the descriptive/metric boundary). The regression test in
``tests/unit/core/agents/test_author_voice_agent.py`` enforces this.

See:
    ADR-074 — Author Voice Storage Contract (binding boundary invariant).
    ADR-055 — Character Voice Contract (the structural parallel mirrored here).
    ADR-035 — Agent output validation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Enumerations from the governed template's output contract. Identical to
# CharacterVoiceEntry (the qualitative vocabulary is voice-generic).
VocabularyLevel = Literal["simple", "moderate", "complex"]
SentenceProfile = Literal["short", "medium", "long", "varied"]
EmotionalRange = Literal["restricted", "moderate", "expressive"]


class AuthorVoiceOutput(BaseModel):
    """Qualitative author-voice profile from a single LLM judgement (ANAL-007).

    The agent's structured output. Descriptive-only (binding boundary:
    ``VoiceMetrics`` / ``AuthorMetrics`` are NEVER on this type — measurement
    is deterministic). The Backend service merges this into an
    :class:`~narrare_core.profiles.author_voice.AuthorVoiceProfile` alongside
    the analyzers' metric blocks.

    Attributes:
        formality: Formality register ``0.0`` (informal/colloquial) - ``1.0``
            (formal/elevated). Pydantic Field enforces bounds (ADR-035).
        vocabulary_level: ``"simple"`` | ``"moderate"`` | ``"complex"``.
        sentence_profile: ``"short"`` | ``"medium"`` | ``"long"`` | ``"varied"``.
        emotional_range: ``"restricted"`` | ``"moderate"`` | ``"expressive"``.
        cultural_regional_markers: Intrinsic markers (dialect, idiom, register
            cues) that aid generation, or ``None`` when none are evident.
        author_examples: 2-4 short curated representative prose passages
            exemplifying the narrator's voice.
    """

    formality: float = Field(default=0.5, ge=0.0, le=1.0)
    vocabulary_level: VocabularyLevel = "moderate"
    sentence_profile: SentenceProfile = "medium"
    emotional_range: EmotionalRange = "moderate"
    cultural_regional_markers: str | None = None
    author_examples: list[str] = Field(default_factory=list)


class AuthorVoiceDeps:
    """Dependencies for AuthorVoiceAgent.

    A plain class (not Pydantic) — mirrors the established ``CharacterVoiceDeps``,
    ``CoreferenceDeps``, ``POVDeps``, ``ReadabilityDeps`` pattern. The governed
    ``author_voice`` template is the system prompt (resolved Mode 1 by the
    Layer-3 service and passed to the agent constructor, RULE-02b). The chapter
    prose + precomputed metrics flow as runtime content in the agent run prompt
    (user channel, RULE-02a category 3); the same data is carried here for
    structured access.

    The agent SEES the metrics as INPUT (deps), NEVER as OUTPUT (binding
    boundary — descriptive-only output). This is the same hybrid pattern
    CharacterVoiceAgent uses: the deterministic half supplies measurements;
    the agent interprets them qualitatively.

    Attributes:
        chapter_prose: The (excerpt of the) author's prose under analysis
            (runtime content; full prose is supplied by the service as the run
            prompt).
        voice_metrics_summary: Precomputed voice-generic metrics, formatted for
            the model (runtime content).
        author_metrics_summary: Precomputed author-specific prose-level metrics,
            formatted for the model (runtime content).
        project_title: Project title (prompt context).
        genre: Project genre (prompt context).
        writing_language: Language code (``"en"``, ``"de"``, ``"fr"``).
        chapter_title: Chapter title (prompt context, when scoped to one).
    """

    def __init__(
        self,
        *,
        chapter_prose: str = "",
        voice_metrics_summary: str = "",
        author_metrics_summary: str = "",
        project_title: str = "",
        genre: str = "",
        writing_language: str = "en",
        chapter_title: str = "",
    ) -> None:
        self.chapter_prose = chapter_prose
        self.voice_metrics_summary = voice_metrics_summary
        self.author_metrics_summary = author_metrics_summary
        self.project_title = project_title
        self.genre = genre
        self.writing_language = writing_language
        self.chapter_title = chapter_title
