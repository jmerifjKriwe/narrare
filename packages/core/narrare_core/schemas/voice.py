"""Voice-generic Pydantic types — measurement + descriptive voice vocabulary.

These types are voice-GENERIC: they describe measurement and qualitative
vocabulary that applies to ANY voice (character voice, author voice, future
series voice). They are NOT character-specific. They originally lived in
``kb/schemas/character.py`` only because ANAL-008 (Character Voice) was the
first consumer; ADR-074 moved them here as the voice-generic SSOT home so
ANAL-007 (Author Voice) and future consumers reuse the same vocabulary
without duplication (RULE-22).

Backward compatibility: ``kb/schemas/character.py`` and
``kb/schemas/__init__.py`` re-export both types, so every existing import
(``from narrare_core.kb.schemas.character import VoiceMetrics, VoiceAnalysis``
and ``from narrare_core.kb.schemas import VoiceMetrics, VoiceAnalysis``)
continues to resolve unchanged. ANAL-008 / WRITE-010 / ANAL-009-Phase-1
stay green with zero import edits.

See:
- ADR-074 (Author Voice Storage Contract — type-reuse decision + Retrofit step 1)
- ADR-055 (Character Voice Contract — original descriptive/metric boundary)
- ADR-021 (Deterministic analysis — metrics are deterministic)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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
