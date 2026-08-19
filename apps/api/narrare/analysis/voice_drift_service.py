"""Voice-drift analysis service — orchestrates ANAL-009 (ADR-073).

The service is the Layer-3 orchestrator for ADR-073's read-only longitudinal
drift pipeline. For each character with a stored ANAL-008 profile that has
``voice_metrics`` and who speaks in ≥1 selected chapter, it loads the
novel's chapters, reads stored profiles through the ADR-050 consumer contract
(``VoiceProfileConsumer.assemble_for_checking()`` — no SSOT bypass), computes
the deterministic per-chapter trend (signal i) + jumps (signal iii), and runs
the governed ``voice_drift`` agent — **one LLM call per character**
(ADR-073 Decision 3/5). The per-character analysis lives in
:mod:`narrare.analysis.voice_drift_pipeline`; prompt resolution in
:mod:`narrare.analysis.voice_drift_prompt`; agent invocation in
:mod:`narrare.analysis.voice_drift_agent_runner`; result assembly in
:mod:`narrare.analysis.voice_drift_results`.

RULE-11 graceful degradation: a character without a stored profile, without
``voice_metrics``, or silent in every selected chapter yields a graceful
``no_profile`` event (never a crash). A project with no profiled characters
yields an empty result, not an error.

Prompt resolution is Mode 1 (composer-driven, ADR-054): the governed
``voice_drift`` system prompt is resolved ONCE per run and reused for every
character's agent instance. No inline f-string feature prompt is assembled
(RULE-02 / RULE-02b). The precomputed trend + jumps + stored descriptive
profile + chapter metadata flow as runtime data in the agent run prompt (user
channel, RULE-02a category 3).

RULE-13 (ADR-065): ``run()`` returns the aggregated response;
``run_stream()`` yields SSE events. The router uses ``run_stream()``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.analysis.schemas_voice_drift import (
    VoiceDriftCharacterResult,
    VoiceDriftEvent,
    VoiceDriftNoProfile,
    VoiceDriftRequest,
    VoiceDriftResponse,
)
from narrare.analysis.voice_drift_pipeline import (
    analyse_character_drift,
    collect_speakers,
    make_no_profile_event,
    resolve_drift_prompt,
)
from narrare_core.profiles.contracts import VoiceProfileConsumer
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.analysis.dialogue_parser import DialogueParser
    from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer

VoiceProfileConsumerProvider = Callable[[UUID], Awaitable[VoiceProfileConsumer]]

logger = structlog.get_logger(__name__)


class CharacterVoiceDriftService:
    """Service for longitudinal character-voice drift analysis (ANAL-009).

    The drift analysis is read-only: it never writes to KB (ADR-073
    Decision 5). Stored profiles are read through
    ``VoiceProfileConsumer.assemble_for_checking()`` only, preserving
    ADR-050's profile-consumer boundary (no SSOT bypass).

    Args:
        novel_repo: Repository for novel access-control + metadata.
        chapter_repo: Repository used to load the novel's chapters.
        model_registry: Shared LLM model registry.
        consumer_provider: Factory for a request-scoped voice-profile
            consumer.
        model_config: Resolved model configuration for the agent call.
        composer: PromptComposer for governed Mode-1 prompt resolution.
        relationship_repo: Optional relationship repository for populating
            ``kb_relationships`` (character relationships help the
            classifier distinguish ``context`` drift from ``inconsistency``).
            When ``None``, degrades gracefully to an empty string (RULE-11).
        invocation_pipeline: Optional invocation governance pipeline.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        chapter_repo: ChapterRepository,
        model_registry: ModelRegistry,
        consumer_provider: VoiceProfileConsumerProvider,
        model_config: ResolvedModelConfig | None = None,
        composer: PromptComposer | None = None,
        relationship_repo: RelationshipRepository | None = None,
        *,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._registry = model_registry
        self._consumer_provider = consumer_provider
        self._config = model_config
        self._composer = composer
        self._relationship_repo = relationship_repo
        self._invocation_pipeline = invocation_pipeline

    async def run(
        self,
        novel_id: UUID,
        user_id: UUID,
        request: VoiceDriftRequest,
    ) -> VoiceDriftResponse:
        """Non-streaming aggregate of :meth:`run_stream` into a :class:`VoiceDriftResponse`."""
        results: list[VoiceDriftCharacterResult] = []
        no_profiles: list[VoiceDriftNoProfile] = []
        async for event in self.run_stream(novel_id, user_id, request):
            if event.event == "character_result" and event.result is not None:
                results.append(event.result)
            elif event.event == "no_profile" and event.no_profile is not None:
                no_profiles.append(event.no_profile)
        return VoiceDriftResponse(
            novel_id=str(novel_id),
            results=results,
            no_profile=no_profiles,
        )

    async def run_stream(
        self,
        novel_id: UUID,
        user_id: UUID,
        request: VoiceDriftRequest,
    ) -> AsyncIterator[VoiceDriftEvent]:
        """Analyse longitudinal voice drift, streaming SSE events.

        Yields a ``"progress"`` event, one ``"character_result"`` or
        ``"no_profile"`` event per character, then a terminal ``"done"``
        event.
        """
        # 1. Resolve novel (access control + metadata).
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        config = self._config
        if config is None:
            raise NotFoundError("Model config", identifier="no_model_config")

        composer = self._composer
        if composer is None:
            raise ConfigurationError(
                "PromptComposer is not configured for voice-drift analysis.",
                code="NO_COMPOSER",
            )

        language = novel.writing_language or "en"

        # 2. Load chapters (specific ids or all chapters in the novel).
        from narrare.analysis.character_voice_kb_writer import load_selected_chapters

        chapter_ids = [UUID(cid) for cid in request.chapter_ids] if request.chapter_ids else None
        chapters = await load_selected_chapters(self._chapter_repo, novel_id, chapter_ids)

        if not chapters:
            logger.info(
                "voice_drift_no_chapters",
                feature_id="analysis_voice_drift",
                novel_id=str(novel_id),
            )
            yield VoiceDriftEvent(
                event="progress",
                progress="No chapters found in the novel.",
            )
            yield VoiceDriftEvent(event="done", is_final=True)
            return

        # 3. Build chapter text + title maps (keyed by str chapter id).
        chapter_texts: dict[str, str] = {str(ch.id): ch.content or "" for ch in chapters}
        chapter_titles: dict[str, str] = {str(ch.id): ch.title or "" for ch in chapters}

        # 4. Read stored profiles via the consumer contract (ADR-050).
        consumer = await self._consumer_provider(novel_id)
        profiles = await consumer.assemble_for_checking(novel_id)

        # Optional character_id filter (scope to one character by profile id).
        if request.character_id is not None:
            profiles = [p for p in profiles if p.character_id == request.character_id]

        profiles_by_name = {p.name: p for p in profiles}

        # 5. Collect all speakers across the selected chapters (parse once).
        parser = self._make_dialogue_parser()
        analyzer = self._make_voice_metrics_analyzer(language)
        all_speakers = collect_speakers(chapters, parser)

        # 6. Determine the character set to iterate.
        if request.character_id is not None:
            # Scoped to one character — iterate only the filtered profiles.
            all_names = sorted(profiles_by_name)
        else:
            all_names = sorted(set(profiles_by_name) | all_speakers)

        if not all_names:
            yield VoiceDriftEvent(
                event="progress",
                progress="No characters to analyse (no profiles, no dialogue).",
            )
            yield VoiceDriftEvent(event="done", is_final=True)
            return

        yield VoiceDriftEvent(
            event="progress",
            progress=(
                f"Analysing voice drift for {len(all_names)} character(s) "
                f"across {len(chapters)} chapter(s)."
            ),
        )

        # 7. Per-character loop. The governed prompt is resolved lazily on
        #    the first analysable character and reused for all (Mode 1,
        #    ADR-054 — one composition per run, N agent calls).
        from narrare_core.analysis.voice_drift_scoring import compute_per_chapter_metrics

        composed_prompt: ComposedPrompt | None = None

        for name in all_names:
            profile = profiles_by_name.get(name)
            if profile is None:
                yield make_no_profile_event(name, "", "no_stored_profile")
                continue
            if profile.voice_metrics is None:
                yield make_no_profile_event(name, profile.character_id, "no_voice_metrics")
                continue

            per_chapter = compute_per_chapter_metrics(
                chapter_texts,
                name,
                parser=parser,
                analyzer=analyzer,
            )
            if not per_chapter:
                yield make_no_profile_event(
                    name, profile.character_id, "no_dialogue_in_selected_chapters"
                )
                continue

            if composed_prompt is None:
                composed_prompt = await resolve_drift_prompt(
                    composer=composer,
                    invocation_pipeline=self._invocation_pipeline,
                    relationship_repo=self._relationship_repo,
                    novel=novel,
                    language=language,
                    novel_id=novel_id,
                    user_id=user_id,
                )

            result = await analyse_character_drift(
                profile=profile,
                per_chapter=per_chapter,
                chapter_titles=chapter_titles,
                composed_prompt=composed_prompt,
                novel=novel,
                language=language,
                model_registry=self._registry,
                model_config=config,
            )
            yield VoiceDriftEvent(event="character_result", result=result)

        logger.info(
            "voice_drift_complete",
            feature_id="analysis_voice_drift",
            novel_id=str(novel_id),
            character_count=len(all_names),
        )
        yield VoiceDriftEvent(event="done", is_final=True)

    # ------------------------------------------------------------------
    # Analyzer construction (overridable for tests)
    # ------------------------------------------------------------------

    def _make_dialogue_parser(self) -> DialogueParser:
        from narrare_core.analysis.dialogue_parser import DialogueParser

        return DialogueParser()

    def _make_voice_metrics_analyzer(self, language: str) -> VoiceMetricsAnalyzer:
        from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer

        return VoiceMetricsAnalyzer(language=language)
