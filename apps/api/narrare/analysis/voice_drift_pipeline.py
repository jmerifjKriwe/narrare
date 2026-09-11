"""Voice-drift pipeline helpers — speaker collection + per-character analysis.

Extracted from ``voice_drift_service.py`` for RULE-04 compliance
(service < 300 lines). This module owns two focused pipeline responsibilities
that would bloat the orchestration service:

1. **Speaker collection** (:func:`collect_speakers`) — parses every chapter
   once to gather the set of attributed speaker names (so the service can
   surface speakers without a stored profile as graceful ``no_profile``
   events, RULE-11).
2. **Per-character analysis** (:func:`analyse_character_drift`) — for one
   analysable character (profile + ``voice_metrics`` + speaks in ≥1 chapter):
   computes the deterministic trend (signal i) + jumps (signal iii), builds
   the chapter metadata, runs the governed agent (1 LLM call), and assembles
   the API result. The deterministic scoring is pure Core
   (:mod:`narrare_core.analysis.voice_drift_scoring`, ADR-021); the agent only
   interprets the trend qualitatively.

See:
    ADR-073 — Character Voice Drift (Decisions 2, 3, 5).
    ADR-021 — Deterministic analysis strategy.
    RULE-04 — Modularise, never compress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from narrare.analysis.schemas_voice_drift import (
    VoiceDriftCharacterResult,
    VoiceDriftEvent,
    VoiceDriftNoProfile,
)
from narrare.analysis.voice_drift_agent_runner import run_voice_drift_agent
from narrare.analysis.voice_drift_results import assemble_voice_drift_result
from narrare_core.agents.character_voice_drift_types import ChapterMeta
from narrare_core.analysis.voice_drift_scoring import (
    detect_adjacent_jumps,
    trend_against_profile,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

    from narrare.chapters.models import Chapter
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.analysis.dialogue_parser import DialogueParser
    from narrare_core.analysis.voice_drift_scoring_types import (
        PerChapterMetrics,
    )
    from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer
    from narrare_core.kb.schemas.character import VoiceMetrics
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.profiles.models import CharacterVoiceProfile
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer


def make_no_profile_event(
    name: str,
    character_id: str,
    reason: str,
) -> VoiceDriftEvent:
    """Build a graceful ``no_profile`` SSE event (RULE-11).

    Args:
        name: The character's canonical name.
        character_id: The stored profile ``character_id``, or ``""`` when the
            character has no stored profile at all.
        reason: Why the character was skipped — ``"no_stored_profile"``,
            ``"no_voice_metrics"``, or ``"no_dialogue_in_selected_chapters"``.
    """
    return VoiceDriftEvent(
        event="no_profile",
        no_profile=VoiceDriftNoProfile(
            character_id=character_id,
            character_name=name,
            reason=reason,
        ),
    )


async def resolve_drift_prompt(
    *,
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    relationship_repo: RelationshipRepository | None,
    novel: object,
    language: str,
    novel_id: UUID,
    user_id: UUID,
) -> ComposedPrompt:
    """Resolve the governed ``voice_drift`` system prompt (Mode 1, lazy).

    Fetches KB relationships (character relationships help the classifier
    distinguish ``context`` drift from ``inconsistency``) and resolves the
    governed prompt via :func:`resolve_voice_drift_prompt`. Called once per
    run on the first analysable character (the result is reused for all).
    """
    from narrare.analysis.voice_drift_prompt import resolve_voice_drift_prompt
    from narrare.writing._relationship_helpers import (
        fetch_formatted_relationships,
    )

    rel_context = await fetch_formatted_relationships(relationship_repo, novel_id)
    return await resolve_voice_drift_prompt(
        composer,
        invocation_pipeline,
        novel=novel,
        language=language,
        novel_id=novel_id,
        user_id=user_id,
        kb_relationships=rel_context.text,
    )


def collect_speakers(chapters: list[Chapter], parser: DialogueParser) -> set[str]:
    """Collect all attributed speaker names across the selected chapters.

    Parses each chapter once (the per-character
    :func:`compute_per_chapter_metrics` re-parses per character — accepted for
    v1; no caching per ADR-073 Decision 5). Speakers with no stored profile
    are surfaced by the service as graceful ``no_profile`` events (RULE-11).
    """
    speakers: set[str] = set()
    for chapter in chapters:
        for utt in parser.parse(chapter.content or ""):
            if utt.speaker:
                speakers.add(utt.speaker)
    return speakers


def make_dialogue_parser() -> DialogueParser:
    """Create the deterministic dialogue parser used by the drift pipeline.

    Owns the analyzer-construction seam next to the pipeline logic that
    consumes it (RULE-04 modularization — the service stays below its size
    limit while construction remains in the analysis layer). Tests patch
    this module function instead of a service method.
    """
    from narrare_core.analysis.dialogue_parser import DialogueParser

    return DialogueParser()


def make_voice_metrics_analyzer(language: str) -> VoiceMetricsAnalyzer:
    """Create the deterministic voice-metrics analyzer for ``language``.

    Construction seam paired with :func:`make_dialogue_parser` — both feed
    :func:`collect_speakers` and
    :func:`narrare_core.analysis.voice_drift_scoring.compute_per_chapter_metrics`.
    """
    from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer

    return VoiceMetricsAnalyzer(language=language)


async def analyse_character_drift(
    *,
    profile: CharacterVoiceProfile,
    per_chapter: list[PerChapterMetrics],
    chapter_titles: Mapping[str, str],
    composed_prompt: ComposedPrompt,
    novel: object,
    language: str,
    model_registry: ModelRegistry,
    model_config: ResolvedModelConfig,
    api_key: str | None = None,
    base_url: str | None = None,
) -> VoiceDriftCharacterResult:
    """Compute trend + jumps, run the agent, and assemble one character's result.

    The deterministic trend (signal i) + jumps (signal iii) are computed via
    :mod:`narrare_core.analysis.voice_drift_scoring` (ADR-021); the governed
    agent (1 LLM call, ADR-073 D3/D5) only interprets the trend qualitatively.
    The result is assembled by
    :func:`narrare.analysis.voice_drift_results.assemble_voice_drift_result`.

    Args:
        profile: The stored profile (carries ``character_id`` + ``name`` +
            ``speech_summary`` + ``voice_metrics``).
        per_chapter: The precomputed per-chapter metrics for this character
            (non-empty — the caller guarantees the character speaks in ≥1
            chapter).
        chapter_titles: Mapping from chapter id (str) to title, for building
            the agent's chapter metadata.
        composed_prompt: The already-resolved governed ``voice_drift``
            :class:`ComposedPrompt` (Mode 1 — resolved once by the service).
        novel: Novel metadata object.
        language: Writing language code.
        model_registry: Model registry used to resolve the configured model.
        model_config: Resolved model configuration.
        api_key: Optional per-user provider API key override (model-routing
            cascade) — forwarded to the agent runner's ``get_model`` call.
        base_url: Optional per-user provider base URL override.

    Returns:
        The API :class:`VoiceDriftCharacterResult` with the deterministic
        trend + jumps + the derived overall score/band + the agent
        classification.
    """
    # Precondition: the service narrows ``profile.voice_metrics is None``
    # into a graceful ``no_voice_metrics`` event before calling this
    # function, so the profile passed in always carries metrics. The cast
    # bridges the caller's narrowing, which is lost when the whole profile
    # object crosses the function boundary.
    trend = trend_against_profile(per_chapter, cast("VoiceMetrics", profile.voice_metrics))
    jumps = detect_adjacent_jumps(per_chapter)
    chapter_meta = [
        ChapterMeta(
            chapter_id=pcm.chapter_id,
            title=chapter_titles.get(pcm.chapter_id, ""),
        )
        for pcm in per_chapter
    ]
    drift = await run_voice_drift_agent(
        composed_prompt=composed_prompt,
        character_name=profile.name,
        descriptive_profile=profile.speech_summary,
        trend=trend,
        jumps=jumps,
        chapter_meta=chapter_meta,
        novel=novel,
        language=language,
        model_registry=model_registry,
        model_config=model_config,
        api_key=api_key,
        base_url=base_url,
    )
    return assemble_voice_drift_result(
        profile=profile,
        trend=trend,
        jumps=jumps,
        drift=drift,
    )
