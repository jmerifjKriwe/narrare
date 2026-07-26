"""Value types for voice_drift_scoring (ANAL-009 / ADR-073 D2).

The pure Pydantic value objects produced and consumed by
:mod:`narrare_core.analysis.voice_drift_scoring`. Split into its own module so
the scoring module stays under the RULE-04 400-line hard limit (modularise, do
not minify) — mirrors the ``*_types.py`` pattern used across the analysis +
agents packages (e.g. ``voice_types.py``, ``character_voice_drift_types.py``).

These are **pure value objects** — no behaviour, no I/O, no LLM. They carry the
deterministic measurements (signal i + signal iii) that the scoring functions
produce and the drift agent consumes.

- :class:`PerChapterMetrics` — per-chapter measured metrics for one character
  (signal i input; chapters where the character is silent are OMITTED, RULE-11).
- :class:`TrendPoint` — one point on the per-chapter match trend (signal i
  output; the always-visible sparkline / heatmap row).
- :class:`JumpPoint` — an adjacent-chapter jump (signal iii output; localises
  where drift began).

See Also
--------
ADR-073 — Character Voice Drift (Decision 2 comparison model).
narrare_core.analysis.voice_drift_scoring — the functions that produce these.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Runtime import (not TYPE_CHECKING): VoiceMetrics is a Pydantic field type on
# PerChapterMetrics — Pydantic resolves field annotations at class-definition
# time via typing.get_type_hints(), so the symbol MUST be importable at runtime
# (mirrors narrare_core.profiles.models, ADR-057 Risk #1). noqa: TC001.
from narrare_core.kb.schemas.character import VoiceMetrics  # noqa: TC001


class PerChapterMetrics(BaseModel):
    """Per-chapter computed metrics for one character (signal i input).

    Produced by :func:`narrare_core.analysis.voice_drift_scoring.compute_per_chapter_metrics`
    for each chapter where the character speaks. Chapters where the character
    is silent are OMITTED from the list (RULE-11 graceful — no artificial
    zeros; ADR-073 Decision 5).

    Attributes:
        chapter_id: The chapter identifier (caller-supplied).
        character_id: The character identifier (caller-supplied).
        metrics: The deterministic VoiceMetrics for this character in this
            chapter (from :class:`VoiceMetricsAnalyzer`).
        utterance_count: How many attributed utterances the character had in
            this chapter (≥ 1 — chapters with 0 are omitted by contract).
    """

    model_config = {"frozen": True}

    chapter_id: str
    character_id: str
    metrics: VoiceMetrics
    utterance_count: int = Field(ge=0)


class TrendPoint(BaseModel):
    """One point on the per-chapter match trend (signal i output).

    Produced by :func:`narrare_core.analysis.voice_drift_scoring.trend_against_profile`.
    The trend is the always-visible sparkline / heatmap row.

    Attributes:
        chapter_id: The chapter identifier.
        match_subscore: Per-chapter match sub-score in ``[0.0, 100.0]``
            (``100.0`` = perfectly matches the stored profile that chapter;
            ``0.0`` when no metric is comparable). Derived from
            :func:`metric_delta_subscore` semantics — ``(1 - mean_distance) * 100``.
        per_metric_deltas: Mapping from metric name to its normalized ``[0, 1]``
            distance vs the profile. Only metrics present on BOTH sides appear
            (mirrors :func:`voice_metric_distances`). Empty when no metric is
            comparable.
        band: The drift-facing severity label (``"stable"`` | ``"minor"`` |
            ``"moderate"`` | ``"major"``) — derived from :func:`band_for_score`
            via :data:`narrare_core.analysis.voice_drift_scoring._VOICE_CHECK_BAND_TO_DRIFT_LABEL`
            so thresholds are identical to WRITE-010 (ADR-073 D4).
    """

    model_config = {"frozen": True}

    chapter_id: str
    match_subscore: float = Field(ge=0.0, le=100.0)
    per_metric_deltas: dict[str, float] = Field(default_factory=dict)
    band: str


class JumpPoint(BaseModel):
    """An adjacent-chapter jump (signal iii output).

    Produced by :func:`narrare_core.analysis.voice_drift_scoring.detect_adjacent_jumps`
    for each pair of consecutive chapters where at least one metric shifted
    beyond the threshold. Jump points localise *where* drift began.

    Attributes:
        from_chapter_id: The earlier chapter of the pair.
        to_chapter_id: The later chapter of the pair.
        jumped_metrics: Which metric(s) shifted beyond the threshold between
            the two chapters (e.g. ``["avg_sentence_length"]``). At least one
            entry — empty jumps are never emitted.
        magnitude: Normalized ``[0, 1]`` magnitude of the jump — the mean of
            the jumped metrics' distances. Higher = sharper jump.
    """

    model_config = {"frozen": True}

    from_chapter_id: str
    to_chapter_id: str
    jumped_metrics: list[str] = Field(min_length=1)
    magnitude: float = Field(ge=0.0, le=1.0)
