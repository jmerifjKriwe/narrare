"""Value types for author_voice_drift_scoring (ANAL-009 Phase 2B / ADR-074).

The pure Pydantic value objects produced and consumed by
:mod:`narrare_core.analysis.author_voice_drift_scoring`. Split into its own
module so the scoring module stays under the RULE-04 400-line hard limit
(modularise, not minify) — mirrors the Phase 1 split
(``voice_drift_scoring_types.py``).

These are **pure value objects** — no behaviour, no I/O, no LLM. They carry the
deterministic per-chapter narrator measurements (VoiceMetrics + AuthorMetrics)
that the author drift scoring functions produce and the
:class:`~narrare_core.agents.author_voice_drift_agent.AuthorVoiceDriftAgent`
consumes.

Where Phase 1's :class:`~narrare_core.analysis.voice_drift_scoring_types.PerChapterMetrics`
carries ONE :class:`VoiceMetrics` block per (character, chapter), this carries
TWO metric blocks per chapter — the narrator's voice-generic metrics AND the
author-specific prose-level metrics — because author drift compares BOTH
(ADR-074).

See Also
--------
ADR-074 — Author Voice Storage Contract (the metric shape).
narrare_core.analysis.author_voice_drift_scoring — the functions that produce
    these.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Runtime imports (not TYPE_CHECKING): both are Pydantic field types on this
# model — Pydantic resolves field annotations at class-definition time via
# typing.get_type_hints(), so the symbols MUST be importable at runtime
# (mirrors voice_drift_scoring_types.py). noqa: TC001.
from narrare_core.analysis.author_metrics import AuthorMetrics
from narrare_core.kb.schemas.character import VoiceMetrics


class PerAuthorChapterMetrics(BaseModel):
    """Per-chapter narrator metrics for author-voice drift (signal i input).

    Produced by
    :func:`narrare_core.analysis.author_voice_drift_scoring.compute_per_chapter_author_metrics`
    for each chapter with non-empty prose. Author drift compares the narrator's
    voice across chapters, so each row carries BOTH the voice-generic
    :class:`VoiceMetrics` (from
    :meth:`~narrare_core.analysis.voice_metrics.VoiceMetricsAnalyzer.analyze_text`)
    AND the author-specific :class:`AuthorMetrics` (from
    :class:`~narrare_core.analysis.author_metrics.AuthorMetricsAnalyzer`) —
    ADR-074 stores both on the :class:`~narrare_core.profiles.author_voice.AuthorVoiceProfile`,
    and both participate in the drift comparison.

    RULE-11 graceful: an empty/blank chapter is OMITTED from the list (no
    artificial zeros — mirrors Phase 1 omitting chapters where the character is
    silent). The metric fields default to all-``None`` blocks so an explicit
    empty row (e.g. in tests) is valid.

    Attributes:
        chapter_id: The chapter identifier (caller-supplied).
        voice_metrics: The deterministic voice-generic metrics for this
            chapter's full prose (narration + dialogue together). Defaults to
            an all-``None`` :class:`VoiceMetrics`.
        author_metrics: The deterministic author-specific prose-level metrics
            for this chapter. Defaults to an all-``None``
            :class:`AuthorMetrics`.
    """

    model_config = {"frozen": True}

    chapter_id: str
    voice_metrics: VoiceMetrics = Field(default_factory=VoiceMetrics)
    author_metrics: AuthorMetrics = Field(default_factory=AuthorMetrics)
