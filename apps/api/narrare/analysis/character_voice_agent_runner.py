"""Character-voice agent invocation helper (Mode 1 + one LLM call).

Extracted from ``character_voice_service.py`` for RULE-04 compliance
(service < 300 lines). Owns the single responsibility of running the
``CharacterVoiceAgent`` with the resolved prompt, formatted dialogue, and
per-character metrics.

See:
    ADR-055 — Character voice storage contract.
    RULE-04 — Modularise, never compress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.analysis.character_voice_kb_writer import (
    build_run_prompt,
    format_attributed_dialogue,
    format_metrics_summary,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.agents.character_voice_types import CharacterVoiceOutput
    from narrare_core.analysis.dialogue_parser import AttributedUtterance
    from narrare_core.kb.schemas.character import VoiceMetrics
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import ComposedPrompt

logger = structlog.get_logger(__name__)


async def run_character_voice_agent(
    *,
    utterances: list[AttributedUtterance],
    metrics: dict[str, VoiceMetrics],
    character_names: list[str],
    novel_title: str,
    novel_genre: str,
    novel_id: UUID,
    language: str,
    model_registry: ModelRegistry,
    model_config: ResolvedModelConfig,
    composed_prompt: ComposedPrompt,
    api_key: str | None = None,
    base_url: str | None = None,
) -> CharacterVoiceOutput:
    """Format runtime content and run one ``CharacterVoiceAgent`` call.

    Args:
        utterances: Attributed chapter dialogue.
        metrics: Per-character deterministic voice metrics.
        character_names: Sorted list of speaking character names.
        novel_title: Novel title for agent deps.
        novel_genre: Novel genre for agent deps.
        novel_id: Novel id (for error logging).
        language: Writing language code.
        model_registry: Model registry used to resolve the configured model.
        model_config: Resolved model configuration.
        composed_prompt: The composed system + user prompt (Mode 1).
        api_key: Optional per-user provider API key override (model-routing
            cascade) — injected into ``ModelRegistry.get_model``.
        base_url: Optional per-user provider base URL override.

    Returns:
        The agent output with per-character voice profiles.
    """
    attributed_dialogue = format_attributed_dialogue(utterances)
    metrics_summary = format_metrics_summary(metrics)
    model = await model_registry.get_model(
        model_config,
        api_key=api_key,
        base_url=base_url,
    )

    from narrare_core.agents.character_voice_agent import CharacterVoiceAgent
    from narrare_core.agents.character_voice_types import CharacterVoiceDeps

    deps = CharacterVoiceDeps(
        attributed_dialogue=attributed_dialogue,
        voice_metrics_summary=metrics_summary,
        character_names=character_names,
        project_title=novel_title,
        genre=novel_genre,
        writing_language=language,
    )
    try:
        agent = CharacterVoiceAgent(model=model, system_prompt=composed_prompt.system)
        output = await agent.run(
            prompt=composed_prompt.user or build_run_prompt(attributed_dialogue, metrics_summary),
            deps=deps,
        )
    except Exception as exc:
        logger.error(
            "character_voice_agent_failed",
            novel_id=str(novel_id),
            error=str(exc),
            exc_info=True,
        )
        raise
    return output
