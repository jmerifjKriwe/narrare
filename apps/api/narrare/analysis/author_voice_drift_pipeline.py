"""Author-voice-drift pipeline helpers — narrator metrics + trend + agent.

Extracted from ``author_voice_drift_service.py`` for RULE-04 compliance
(service < 300 lines). This module owns the single-narrator analysis core of
the ADR-074 read-only pipeline, split into two focused steps so the service
can keep the graceful ``no_profile`` ordering (resolve the governed prompt
ONLY once prose is confirmed):

1. :func:`compute_author_voice_per_chapter` — deterministic per-chapter
   narrator metrics (voice + author, ADR-021) over the full prose. Returns an
   empty list when no chapter has prose (the caller emits a graceful
   ``no_profile`` event, RULE-11).
2. :func:`analyse_author_voice_drift` — for chapters with prose: computes the
   narrator trend (signal i) + adjacent jumps (signal iii) against the stored
   metric group, builds the chapter metadata + the rendered descriptive
   profile, runs the governed ``author_voice_drift`` agent (**one LLM call** —
   ADR-073 Decision 5 cardinality applied to ADR-074), and assembles the API
   result. The deterministic scoring is pure Core (ADR-021); the agent only
   interprets the trend qualitatively (ADR-073 Decision 2).

:func:`make_author_voice_drift_no_profile_event` builds the graceful skip
event. This is the narrator-scoped mirror of Phase 1's
:mod:`narrare.analysis.voice_drift_pipeline` (singular narrator in place of
the per-character loop).

See:
    ADR-074 — Author Voice Storage Contract.
    ADR-073 — Character Voice Drift (Decisions 2, 3, 5 — the Phase 1 parallel
        mirrored here for the narrator).
    ADR-021 — Deterministic analysis strategy.
    RULE-04 — Modularise, never compress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.analysis.author_voice_drift_agent_runner import (
    run_author_voice_drift_agent,
)
from narrare.analysis.author_voice_drift_results import (
    assemble_author_voice_drift_result,
)
from narrare.analysis.schemas_author_voice_drift import (
    AuthorVoiceDriftEvent,
    AuthorVoiceDriftNoProfile,
)
from narrare_core.agents.character_voice_drift_types import ChapterMeta
from narrare_core.analysis.author_voice_drift_scoring import (
    compute_per_chapter_author_metrics,
    detect_adjacent_author_jumps,
    trend_against_author_profile,
)
from narrare_core.profiles.author_voice import render_author_voice_for_generation

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftResult
    from narrare.chapters.models import Chapter
    from narrare_core.analysis.author_metrics import AuthorMetrics, AuthorMetricsAnalyzer
    from narrare_core.analysis.author_voice_drift_scoring_types import (
        PerAuthorChapterMetrics,
    )
    from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer
    from narrare_core.kb.schemas.character import VoiceMetrics
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.profiles.author_voice import AuthorVoiceProfile
    from narrare_core.prompts.composer import ComposedPrompt


def make_author_voice_drift_no_profile_event(reason: str) -> AuthorVoiceDriftEvent:
    """Build a graceful ``no_profile`` SSE event (RULE-11).

    Args:
        reason: Why the narrator was skipped — ``"no_stored_profile"``,
            ``"no_profile_metrics"``, or ``"no_chapters_with_prose"``.
    """
    return AuthorVoiceDriftEvent(
        event="no_profile",
        no_profile=AuthorVoiceDriftNoProfile(reason=reason),
    )


def compute_author_voice_per_chapter(
    chapters: Sequence[Chapter],
    language: str,
) -> list[PerAuthorChapterMetrics]:
    """Compute the deterministic per-chapter narrator metrics (ADR-021).

    Builds the chapter-text map (keyed by str chapter id, matching
    ``TrendPoint.chapter_id``), constructs the voice + author analyzers, and
    delegates to
    :func:`narrare_core.analysis.author_voice_drift_scoring.compute_per_chapter_author_metrics`.
    Chapters with empty/blank prose are omitted by the scoring layer
    (RULE-11 graceful — no artificial zeros), so an empty result means no
    chapter had prose (the caller emits a ``no_profile`` event).

    Args:
        chapters: The novel's chapters (narration + dialogue together).
        language: Writing language code (forwarded to the voice analyzer).

    Returns:
        Ordered per-chapter narrator metrics; empty when no chapter has prose.
    """
    chapter_texts: dict[str, str] = {str(ch.id): ch.content or "" for ch in chapters}
    return compute_per_chapter_author_metrics(
        chapter_texts,
        voice_analyzer=_make_voice_metrics_analyzer(language),
        author_analyzer=_make_author_metrics_analyzer(),
    )


async def analyse_author_voice_drift(
    *,
    chapters: Sequence[Chapter],
    per_chapter: list[PerAuthorChapterMetrics],
    profile: AuthorVoiceProfile,
    profile_voice_metrics: VoiceMetrics,
    profile_author_metrics: AuthorMetrics,
    composed_prompt: ComposedPrompt,
    novel: object,
    language: str,
    novel_id: UUID,
    model_registry: ModelRegistry,
    model_config: ResolvedModelConfig,
) -> AuthorVoiceDriftResult:
    """Compute the narrator trend + jumps, run the agent, assemble the result.

    The deterministic narrator trend (signal i) + adjacent jumps (signal iii)
    are computed via :mod:`narrare_core.analysis.author_voice_drift_scoring`
    (ADR-021) against the stored metric group (voice + author); the governed
    ``author_voice_drift`` agent (1 LLM call, ADR-073 D3/D5 applied to
    ADR-074) only interprets the trend qualitatively (ADR-073 D2). The stored
    *descriptive* profile is rendered for the agent — metrics NEVER reach the
    LLM as raw numbers (ADR-074 binding preserved on the author-drift path).
    The result is assembled by
    :func:`narrare.analysis.author_voice_drift_results.assemble_author_voice_drift_result`.

    Args:
        chapters: The novel's chapters (for building the agent chapter
            metadata — title lookup keyed by str chapter id).
        per_chapter: The precomputed per-chapter author metrics (non-empty —
            the caller guarantees >=1 chapter with prose).
        profile: The stored :class:`AuthorVoiceProfile` (carries the
            descriptive profile rendered for the agent).
        profile_voice_metrics: The stored voice-generic metrics block (the
            trend baseline, signal i).
        profile_author_metrics: The stored author-specific metrics block.
        composed_prompt: The already-resolved governed ``author_voice_drift``
            :class:`ComposedPrompt` (Mode 1 — resolved once by the service).
        novel: Novel metadata object (title, genre read via getattr).
        language: Writing language code.
        novel_id: Novel id (carried onto the result; used for agent error
            logging).
        model_registry: Model registry used to resolve the configured model.
        model_config: Resolved model configuration.

    Returns:
        The API :class:`AuthorVoiceDriftResult` with the deterministic trend
        + jumps + the derived overall score/band + the agent classification.
    """
    chapter_titles: dict[str, str] = {str(ch.id): ch.title or "" for ch in chapters}
    trend = trend_against_author_profile(
        per_chapter,
        profile_voice_metrics,
        profile_author_metrics,
    )
    jumps = detect_adjacent_author_jumps(per_chapter)
    descriptive_profile = render_author_voice_for_generation(profile)
    chapter_meta = [
        ChapterMeta(
            chapter_id=pcm.chapter_id,
            title=chapter_titles.get(pcm.chapter_id, ""),
        )
        for pcm in per_chapter
    ]
    drift = await run_author_voice_drift_agent(
        composed_prompt=composed_prompt,
        descriptive_profile=descriptive_profile,
        trend=trend,
        jumps=jumps,
        chapter_meta=chapter_meta,
        novel=novel,
        language=language,
        novel_id=novel_id,
        model_registry=model_registry,
        model_config=model_config,
    )
    return assemble_author_voice_drift_result(
        novel_id=novel_id,
        trend=trend,
        jumps=jumps,
        drift=drift,
    )


def _make_voice_metrics_analyzer(language: str) -> VoiceMetricsAnalyzer:
    """Construct the voice-generic analyzer (overridable seam for tests)."""
    from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer

    return VoiceMetricsAnalyzer(language=language)  # type: ignore[arg-type]


def _make_author_metrics_analyzer() -> AuthorMetricsAnalyzer:
    """Construct the author-specific prose-level analyzer (test seam)."""
    from narrare_core.analysis.author_metrics import AuthorMetricsAnalyzer

    return AuthorMetricsAnalyzer()
