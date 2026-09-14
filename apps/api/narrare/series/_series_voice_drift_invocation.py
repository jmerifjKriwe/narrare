"""Invocation assembly for the Series Voice Drift pipeline (ADR-086 L29).

Extracted from ``series_voice_drift_service.py`` (RULE-04: the ADR-086
``ensure_resolved`` addition crossed the 300-line service limit —
modularize, don't compress). One responsibility: run ONE series-voice-drift
invocation over a band's chapters against the SERIES baseline and return the
assembled :class:`AuthorVoiceDriftResponse` — no ownership checks, no profile
persistence, no snapshot store (all stay in the service / wrapper layers).

Reuses the EXISTING novel-level analysis drift pipeline in the SAME order the
service called it inline (timing-only migration: WHAT unchanged):

    :func:`compute_author_voice_per_chapter` — deterministic per-chapter
        narrator metrics (voice + author, ADR-021).
    :func:`resolve_author_voice_drift_prompt` — Mode-1 governed
        ``author_voice_drift`` system prompt.
    :func:`analyse_author_voice_drift` — trend + jumps + agent (1 LLM call) +
        result assembly, fed the resolved model triple (config + credentials)
        from the lazy routing cascade (ADR-086).

RULE-11 graceful degradation: chapters without prose yield a graceful
``no_profile`` response (no LLM call) — mirroring the novel-level service.

See:
    ADR-086 L29 — the lazy-resolution slice that extracted this module.
    ADR-078 — Series Voice Hierarchy (Delta model).
    ADR-074 — Author Voice Storage Contract (the pipeline reused).
    RULE-01b/02/04/06.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.analysis.author_voice_drift_pipeline import (
    analyse_author_voice_drift,
    compute_author_voice_per_chapter,
)
from narrare.analysis.author_voice_drift_prompt import resolve_author_voice_drift_prompt
from narrare.analysis.schemas_author_voice_drift import (
    AuthorVoiceDriftNoProfile,
    AuthorVoiceDriftResponse,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.models import Chapter
    from narrare.novels.models import Novel
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.analysis.author_metrics import AuthorMetrics
    from narrare_core.kb.schemas.character import VoiceMetrics
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.model_routing import ResolvedModel
    from narrare_core.profiles.author_voice import AuthorVoiceProfile
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


async def run_series_voice_drift_invocation(
    *,
    registry: ModelRegistry,
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    resolved_model: ResolvedModel,
    chapters: list[Chapter],
    profile: AuthorVoiceProfile,
    profile_voice_metrics: VoiceMetrics,
    profile_author_metrics: AuthorMetrics,
    novel: Novel,
    language: str,
    novel_id: UUID,
    user_id: UUID,
) -> AuthorVoiceDriftResponse:
    """Run one series-voice-drift invocation against the SERIES baseline.

    Per-chapter metrics → prose guard → governed prompt → one agent call →
    aggregate assembly (the reused analysis drift pipeline steps, verbatim
    order). The resolved model triple arrives pre-resolved by the caller
    (ADR-086 first-use semantics — this module never touches the routing
    cascade) and flows into ``ModelRegistry.prepare`` verbatim.

    Args:
        registry: Model registry for the AuthorVoiceDriftAgent.
        composer: PromptComposer for the governed author_voice_drift prompt.
        invocation_pipeline: Optional InvocationPipeline for evidence.
        resolved_model: The lazily resolved routing triple (config +
            credentials) — flows into ``ModelRegistry.prepare`` verbatim.
        chapters: The band's loaded chapters (already filtered by the
            caller's ``chapter_ids`` selection).
        profile: The SERIES voice profile (the drift baseline).
        profile_voice_metrics: The baseline's voice metric group (extracted
            by the caller's guard).
        profile_author_metrics: The baseline's author metric group.
        novel: The member novel (metadata read for the prompt context).
        language: Writing language code (novel → series fallback chain).
        novel_id: The novel id (invocation context project_id).
        user_id: The requesting user id (invocation context user_id).

    Returns:
        The aggregate drift response (result set, or a graceful
        ``no_profile`` when no chapter carries prose).
    """
    # 1. Deterministic per-chapter narrator metrics (ADR-021). No chapter
    #    with prose → graceful no_profile (mirrors the novel-level service).
    per_chapter = compute_author_voice_per_chapter(chapters, language)
    if not per_chapter:
        logger.info(
            "series_voice_drift_no_profile",
            feature_id="series_voice_drift",
            novel_id=str(novel_id),
            reason="no_chapters_with_prose",
        )
        return AuthorVoiceDriftResponse(
            novel_id=str(novel_id),
            no_profile=AuthorVoiceDriftNoProfile(reason="no_chapters_with_prose"),
        )

    # 2. Resolve the governed author_voice_drift system prompt (Mode 1,
    #    ADR-054) — one composition per check (only after prose confirmed).
    composed_prompt = await resolve_author_voice_drift_prompt(
        composer,
        invocation_pipeline,
        novel=novel,
        language=language,
        novel_id=novel_id,
        user_id=user_id,
    )

    # 3. Trend (signal i) + jumps (signal iii) + agent (1 LLM call) + result
    #    assembly against the SERIES baseline. The descriptive profile +
    #    precomputed trend + jumps + chapter metadata flow as runtime content
    #    (user channel, RULE-02a category 3); metrics never reach the LLM as
    #    raw numbers (ADR-074 binding preserved).
    result = await analyse_author_voice_drift(
        chapters=chapters,
        per_chapter=per_chapter,
        profile=profile,
        profile_voice_metrics=profile_voice_metrics,
        profile_author_metrics=profile_author_metrics,
        composed_prompt=composed_prompt,
        novel=novel,
        language=language,
        novel_id=novel_id,
        model_registry=registry,
        model_config=resolved_model.config,
        api_key=resolved_model.api_key,
        base_url=resolved_model.base_url,
    )
    logger.info(
        "series_voice_drift_complete",
        feature_id="series_voice_drift",
        novel_id=str(novel_id),
        chapter_count=len(chapters),
    )
    return AuthorVoiceDriftResponse(novel_id=str(novel_id), result=result)
