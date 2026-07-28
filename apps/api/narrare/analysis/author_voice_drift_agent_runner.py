"""Author-voice-drift agent invocation helper (Mode 1 + one LLM call).

This module owns ANAL-009 Phase 2B's agent-boundary work: building the
:class:`AuthorVoiceDriftDeps`, formatting the run prompt (user channel) from
the rendered descriptive profile + precomputed trend + jumps + chapter
metadata, and calling :class:`AuthorVoiceDriftAgent.run`. Keeping this
separate from ``author_voice_drift_service.py`` preserves RULE-04/06: the
service orchestrates the pipeline, while this helper performs the focused
agent-boundary work for the single narrator.

The governed ``author_voice_drift`` system prompt is resolved ONCE by the
service (via
:func:`narrare.analysis.author_voice_drift_prompt.resolve_author_voice_drift_prompt`)
and passed in as ``composed_prompt`` — the agent constructor binds
``system_prompt`` at construction (pydantic-ai). Author voice is one narrator
per novel, so exactly ONE agent call runs per request (ADR-073 Decision 5
cardinality, applied to ADR-074).

See:
    ADR-074 — Author Voice Storage Contract.
    ADR-073 — Character Voice Drift (Decision 3 agent role, Decision 5 scope).
    ADR-021 — Deterministic analysis (the agent interprets the precomputed
        trend; it never recomputes metrics).
    RULE-04 — Modularise, never compress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.analysis.author_voice_drift_runtime_content import (
    build_author_voice_drift_run_prompt,
)
from narrare_core.agents.author_voice_drift_agent import AuthorVoiceDriftAgent
from narrare_core.agents.author_voice_drift_types import AuthorVoiceDriftDeps

if TYPE_CHECKING:
    from narrare_core.agents.character_voice_drift_types import (
        ChapterMeta,
        JumpPoint,
        TrendPoint,
        VoiceDriftResult,
    )
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import ComposedPrompt

logger = structlog.get_logger(__name__)


async def run_author_voice_drift_agent(
    *,
    composed_prompt: ComposedPrompt,
    descriptive_profile: str,
    trend: list[TrendPoint],
    jumps: list[JumpPoint],
    chapter_meta: list[ChapterMeta],
    novel: object,
    language: str,
    novel_id: object,
    model_registry: ModelRegistry,
    model_config: ResolvedModelConfig,
) -> VoiceDriftResult:
    """Run the author-voice-drift agent for the narrator (one LLM call).

    Args:
        composed_prompt: The already-resolved governed ``author_voice_drift``
            :class:`ComposedPrompt` (system + user channels, Mode 1).
        descriptive_profile: The stored *descriptive* author-voice profile
            (rendered via
            :func:`render_author_voice_for_generation`) — the profile the
            agent classifies against. Metrics NEVER reach the LLM as raw
            numbers (ADR-074 binding preserved on the author-drift path).
        trend: The precomputed per-chapter match trend (signal i) from
            :func:`trend_against_author_profile` (author-metric deltas merged).
        jumps: The precomputed adjacent-chapter jump points (signal iii) from
            :func:`detect_adjacent_author_jumps`.
        chapter_meta: Per-chapter metadata (id + title + optional summary)
            for the chapters in the trend.
        novel: Novel metadata object (title, genre read via getattr).
        language: Writing language code.
        novel_id: Novel id (for error logging).
        model_registry: Model registry used to resolve the configured model.
        model_config: Resolved model configuration.

    Returns:
        The agent's :class:`VoiceDriftResult` qualitative classification (the
        OUTPUT shape is reused from Phase 1 — ADR-073 D3 locked shape applied
        to the narrator trend).
    """
    deps = AuthorVoiceDriftDeps(
        descriptive_profile=descriptive_profile,
        trend=trend,
        jumps=jumps,
        chapter_meta=chapter_meta,
        project_title=str(getattr(novel, "title", "")),
        genre=str(getattr(novel, "genre", "") or ""),
        writing_language=language,
    )
    run_prompt = build_author_voice_drift_run_prompt(
        descriptive_profile=descriptive_profile,
        trend=trend,
        jumps=jumps,
        chapter_meta=chapter_meta,
    )

    model = await model_registry.get_model(model_config)
    try:
        agent = AuthorVoiceDriftAgent(
            model=model,
            system_prompt=composed_prompt.system,
        )
        output = await agent.run(
            prompt=composed_prompt.user or run_prompt,
            deps=deps,
        )
    except Exception as exc:
        logger.error(
            "author_voice_drift_agent_failed",
            novel_id=str(novel_id),
            error=str(exc),
            exc_info=True,
        )
        raise
    return output
