"""Voice-drift agent invocation helper (one LLM call per character).

This module owns ANAL-009's agent-boundary work: building the
:class:`CharacterVoiceDriftDeps`, formatting the run prompt (user channel),
and calling :class:`CharacterVoiceDriftAgent.run`. Keeping this separate from
``voice_drift_service.py`` preserves RULE-04/06: the service orchestrates the
per-character loop, while this helper performs the focused agent-boundary
work for ONE character.

The governed ``voice_drift`` system prompt is resolved ONCE by the service
(via :func:`narrare.analysis.voice_drift_prompt.resolve_voice_drift_prompt`)
and passed in as ``composed_prompt`` — the agent constructor binds
``system_prompt`` at construction (pydantic-ai), so the same resolved system
prompt is reused for every character's agent instance (no per-character
re-composition, ADR-054 Mode 1).

See:
    ADR-073 — Character Voice Drift (Decision 3 agent role, Decision 5
        cardinality — 1 call per character).
    ADR-021 — Deterministic analysis (the agent interprets the precomputed
        trend; it never recomputes metrics).
    RULE-04 — Modularise, never compress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.analysis.voice_drift_runtime_content import build_run_prompt
from narrare_core.agents.character_voice_drift_agent import CharacterVoiceDriftAgent
from narrare_core.agents.character_voice_drift_types import (
    CharacterVoiceDriftDeps,
    VoiceDriftResult,
)

if TYPE_CHECKING:
    from narrare_core.agents.character_voice_drift_types import (
        ChapterMeta,
        JumpPoint,
        TrendPoint,
    )
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import ComposedPrompt

logger = structlog.get_logger(__name__)


async def run_voice_drift_agent(
    *,
    composed_prompt: ComposedPrompt,
    character_name: str,
    descriptive_profile: str,
    trend: list[TrendPoint],
    jumps: list[JumpPoint],
    chapter_meta: list[ChapterMeta],
    novel: object,
    language: str,
    model_registry: ModelRegistry,
    model_config: ResolvedModelConfig,
    api_key: str | None = None,
    base_url: str | None = None,
) -> VoiceDriftResult:
    """Run the drift agent for one character (one LLM call).

    Args:
        composed_prompt: The already-resolved governed ``voice_drift``
            :class:`ComposedPrompt` (system + user channels, Mode 1). Reused
            across all characters in a single run (resolved once by the
            service).
        character_name: The canonical name of the character being classified.
        descriptive_profile: The stored *descriptive* voice profile
            (``speech_summary``) — the profile the agent classifies against.
        trend: The precomputed per-chapter match trend (signal i) from
            :func:`trend_against_profile`.
        jumps: The precomputed adjacent-chapter jump points (signal iii)
            from :func:`detect_adjacent_jumps`.
        chapter_meta: Per-chapter metadata (id + title + optional summary)
            for the chapters in the trend.
        novel: Novel metadata object (title, genre read via getattr).
        language: Writing language code.
        model_registry: Model registry used to resolve the configured model.
        model_config: Resolved model configuration.
        api_key: Optional per-user provider API key override (model-routing
            cascade) — injected into ``ModelRegistry.get_model``.
        base_url: Optional per-user provider base URL override.

    Returns:
        The agent's :class:`VoiceDriftResult` qualitative classification.
    """
    deps = CharacterVoiceDriftDeps(
        character_name=character_name,
        descriptive_profile=descriptive_profile,
        trend=trend,
        jumps=jumps,
        chapter_meta=chapter_meta,
        project_title=str(getattr(novel, "title", "")),
        genre=str(getattr(novel, "genre", "") or ""),
        writing_language=language,
    )
    run_prompt = build_run_prompt(
        character_name=character_name,
        descriptive_profile=descriptive_profile,
        trend=trend,
        jumps=jumps,
        chapter_meta=chapter_meta,
    )

    model = await model_registry.get_model(
        model_config,
        api_key=api_key,
        base_url=base_url,
    )
    try:
        agent = CharacterVoiceDriftAgent(
            model=model,
            system_prompt=composed_prompt.system,
        )
        output = await agent.run(
            prompt=composed_prompt.user or run_prompt,
            deps=deps,
        )
    except Exception as exc:
        logger.error(
            "voice_drift_agent_failed",
            character_name=character_name,
            error=str(exc),
            exc_info=True,
        )
        raise
    return output
