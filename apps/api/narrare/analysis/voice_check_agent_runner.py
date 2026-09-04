"""Voice-check agent invocation helper (Mode 1 + one LLM call).

This module owns WRITE-010's governed prompt resolution, runtime-content
formatting, and ``CharacterVoiceCheckerAgent`` call. Keeping this separate from
``voice_check_service.py`` preserves RULE-04/06: the service orchestrates, while
this helper performs the focused agent-boundary work.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.analysis.voice_check_prompt import resolve_voice_check_prompt
from narrare.analysis.voice_check_runtime_content import (
    build_run_prompt,
    format_attributed_dialogue,
    format_descriptive_profiles,
    format_metric_delta_summary,
)
from narrare_core.agents.character_voice_checker_agent import CharacterVoiceCheckerAgent
from narrare_core.agents.character_voice_checker_types import CharacterVoiceCheckerDeps
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from uuid import UUID

    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare_core.agents.character_voice_checker_types import CharacterVoiceCheckerEntry
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.analysis.voice_types import AttributedUtterance
    from narrare_core.kb.schemas.character import VoiceMetrics
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.profiles.models import CharacterVoiceProfile
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


async def run_voice_checker_agent(
    *,
    utterances: Sequence[AttributedUtterance],
    current_metrics: Mapping[str, VoiceMetrics],
    profiles_by_name: Mapping[str, CharacterVoiceProfile],
    checkable: Sequence[str],
    novel: object,
    chapter: object,
    language: str,
    novel_id: UUID,
    user_id: UUID,
    model_registry: ModelRegistry,
    model_config: ResolvedModelConfig,
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    relationship_repo: RelationshipRepository | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict[str, CharacterVoiceCheckerEntry]:
    """Resolve the governed prompt and run one checker-agent call.

    Args:
        utterances: Attributed chapter dialogue.
        current_metrics: Current deterministic metrics by speaking character.
        profiles_by_name: Stored profiles returned by the checking consumer.
        checkable: Speaking characters with stored profiles.
        novel: Novel metadata object.
        chapter: Chapter metadata object.
        language: Writing language code.
        novel_id: Project id for prompt invocation context.
        user_id: Authenticated user id for prompt invocation context.
        model_registry: Model registry used to resolve the configured model.
        model_config: Resolved model configuration.
        composer: PromptComposer for Mode-1 prompt resolution.
        invocation_pipeline: Optional invocation governance pipeline.
        relationship_repo: Optional relationship repository for populating
            ``kb_relationships`` (character relationships help the checker
            evaluate dialogue-tone consistency). When ``None``, degrades
            gracefully to an empty string (RULE-11).
        api_key: Optional per-user provider API key override (model-routing
            cascade) — injected into ``ModelRegistry.prepare``.
        base_url: Optional per-user provider base URL override.

    Returns:
        Mapping from character name to qualitative checker entry.
    """
    # Fetch KB relationships for relationship-aware voice checking
    # (character relationships help the checker evaluate whether
    # dialogue tone is consistent with established dynamics). Reuses
    # the writing-pipeline helper; degrades to "" when no repo is
    # wired (RULE-11).
    from narrare.writing._relationship_helpers import (
        fetch_formatted_relationships,
    )

    rel_context = await fetch_formatted_relationships(relationship_repo, novel_id)

    composed_prompt = await resolve_voice_check_prompt(
        composer,
        invocation_pipeline,
        novel=novel,
        chapter=chapter,
        language=language,
        novel_id=novel_id,
        user_id=user_id,
        kb_relationships=rel_context.text,
    )

    attributed_dialogue = format_attributed_dialogue(utterances)
    descriptive_profiles = format_descriptive_profiles(
        [profiles_by_name[name] for name in checkable]
    )
    stored_metrics: dict[str, VoiceMetrics] = {}
    for name in checkable:
        metrics = profiles_by_name[name].voice_metrics
        if metrics is not None:
            stored_metrics[name] = metrics
    metric_delta = format_metric_delta_summary(stored_metrics, current_metrics, checkable)
    deps = CharacterVoiceCheckerDeps(
        attributed_dialogue=attributed_dialogue,
        descriptive_profile_summary=descriptive_profiles,
        metric_delta_summary=metric_delta,
        character_names=list(checkable),
        project_title=str(getattr(novel, "title", "")),
        genre=str(getattr(novel, "genre", "") or ""),
        writing_language=language,
        chapter_title=str(getattr(chapter, "title", "") or ""),
    )

    # Single assembly point (Task 6a-2 — Task 4/5 pattern): model + intent-aware
    # runtime settings + usage limits as one coherent triple, so the thinking
    # policy actually reaches this call. No run-limit resolver is wired on
    # this path, so ``usage_limits`` is ``None`` (no output caps).
    prepared = await model_registry.prepare(
        model_config,
        intent=LLMIntent.VOICE,
        api_key=api_key,
        base_url=base_url,
    )
    try:
        agent = CharacterVoiceCheckerAgent(
            model=prepared.model, system_prompt=composed_prompt.system
        )
        output = await agent.run(
            prompt=composed_prompt.user
            or build_run_prompt(attributed_dialogue, descriptive_profiles, metric_delta),
            deps=deps,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )
    except Exception as exc:
        logger.error(
            "voice_check_agent_failed",
            chapter_id=str(getattr(chapter, "id", "")),
            error=str(exc),
            exc_info=True,
        )
        raise

    return {entry.character_name: entry for entry in output.characters}
