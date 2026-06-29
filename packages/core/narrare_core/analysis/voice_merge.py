"""Pure merge helper — agent qualitative output + deterministic metrics -> VoiceAnalysis.

Maps a :class:`~narrare_core.agents.character_voice_types.CharacterVoiceEntry`
(the LLM's qualitative judgement for one character) together with the
deterministic :class:`~narrare_core.kb.schemas.character.VoiceMetrics` (from
:class:`~narrare_core.analysis.voice_metrics.VoiceMetricsAnalyzer`) into a
single :class:`~narrare_core.kb.schemas.character.VoiceAnalysis` — the Layer-0
storage type that ANAL-008 persists on
``KBEntity.metadata["speech"]["voice_analysis"]``.

ADR-055 persistence scope: ``distinctiveness_notes`` is a **per-run comparison
artifact** (relative to whichever other characters were analysed in the same
invocation). It is NOT an intrinsic property of the character and is therefore
**excluded** from the persisted :class:`VoiceAnalysis`. The Layer-3 backend
surfaces it to the UI panel as a review aid but never writes it to KB.

This function is **pure** — no I/O, no DB, no side effects. The Backend
(Layer 3) calls it and then writes the resulting :class:`VoiceAnalysis` to KB
+ bumps ``updated_at`` (ADR-055 Consequences).

See Also
--------
ADR-055 — Character voice storage contract (Decision 1 persistence scope).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.kb.schemas.character import VoiceAnalysis, VoiceMetrics

if TYPE_CHECKING:
    from narrare_core.agents.character_voice_types import CharacterVoiceEntry

__all__ = ["merge_character_voice"]


def merge_character_voice(
    entry: CharacterVoiceEntry,
    metrics: VoiceMetrics | None = None,
) -> VoiceAnalysis:
    """Merge a character's qualitative profile + deterministic metrics into VoiceAnalysis.

    Maps the intrinsic qualitative fields (formality, vocabulary_level,
    sentence_profile, emotional_range, cultural_regional_markers,
    voice_examples) and the deterministic metrics (-> ``voice_metrics``) into
    the Layer-0 :class:`VoiceAnalysis` storage type.

    ``distinctiveness_notes`` is deliberately **excluded** — it is a per-run
    comparison artifact, not an intrinsic property (ADR-055 Decision 1
    persistence scope).

    Args:
        entry: The agent's qualitative voice profile for one character.
        metrics: The deterministic :class:`VoiceMetrics` for the same
            character (from :class:`VoiceMetricsAnalyzer`), or ``None`` when
            no metrics were computed (e.g. the character had no attributed
            dialogue). Gracefully degrades to ``voice_metrics=None``
            (RULE-11).

    Returns:
        A :class:`VoiceAnalysis` ready to persist on
        ``speech.voice_analysis``.
    """
    return VoiceAnalysis(
        formality=entry.formality,
        vocabulary_level=entry.vocabulary_level,
        sentence_profile=entry.sentence_profile,
        emotional_range=entry.emotional_range,
        cultural_regional_markers=entry.cultural_regional_markers,
        voice_examples=list(entry.voice_examples) if entry.voice_examples else None,
        voice_metrics=metrics,
    )
