"""Voice-check analysis service — orchestrates WRITE-010.

The service is the Layer-3 orchestrator for ADR-057's read-only hybrid
checking pipeline. It loads the chapter, parses attributed dialogue, computes
current metrics, reads stored profiles through the ADR-050 consumer contract,
runs the governed ``voice_check`` agent once for all checkable characters, and
streams per-character result events.

Focused helper modules own prompt resolution, runtime-content formatting,
agent invocation, and result assembly so this service stays below the RULE-04
hard limit without compressing readability.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.analysis.schemas_voice_check import VoiceCheckStreamEvent
from narrare.analysis.voice_check_agent_runner import run_voice_checker_agent
from narrare.analysis.voice_check_results import assemble_voice_check_result
from narrare_core.profiles.contracts import VoiceProfileConsumer
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from narrare._app.dependencies_services import ModelResolution
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.analysis.dialogue_parser import DialogueParser
    from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.model_routing import ResolvedModel
    from narrare_core.prompts.composer import PromptComposer

VoiceProfileConsumerProvider = Callable[[UUID], Awaitable[VoiceProfileConsumer]]

logger = structlog.get_logger(__name__)


class CharacterVoiceCheckerService:
    """Service for character-voice consistency checking (WRITE-010).

    The checker is read-only: it never writes to KB. Stored profiles are read
    through ``VoiceProfileConsumer.assemble_for_checking()`` only, preserving
    ADR-050's profile-consumer boundary.

    Args:
        novel_repo: Repository used for novel access-control and metadata.
        chapter_repo: Repository used to load the checked chapter.
        model_registry: Shared LLM model registry.
        consumer_provider: Factory for a request-scoped voice-profile consumer.
        model_resolution: Lazy per-user model resolution (ADR-086) — the
            routing cascade resolves on first use, never at construction.
        composer: PromptComposer for governed Mode-1 prompt resolution.
        relationship_repo: Optional relationship repository for populating
            ``kb_relationships`` (character relationships help the checker
            evaluate dialogue-tone consistency). When ``None``, degrades
            gracefully to an empty string (RULE-11).
        invocation_pipeline: Optional invocation governance pipeline.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        chapter_repo: ChapterRepository,
        model_registry: ModelRegistry,
        consumer_provider: VoiceProfileConsumerProvider,
        model_resolution: ModelResolution,
        composer: PromptComposer | None = None,
        relationship_repo: RelationshipRepository | None = None,
        *,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._registry = model_registry
        self._consumer_provider = consumer_provider
        self._model_resolution = model_resolution
        self._resolved: ResolvedModel | None = None
        self._composer = composer
        self._relationship_repo = relationship_repo
        self._invocation_pipeline = invocation_pipeline

    async def ensure_resolved(self) -> ResolvedModel:
        """Resolve the per-user model routing once; idempotent (ADR-086)."""
        if self._resolved is None:
            self._resolved = await self._model_resolution.resolve()
        return self._resolved

    async def check(
        self,
        chapter_id: UUID,
        user_id: UUID,
    ) -> AsyncIterator[VoiceCheckStreamEvent]:
        """Check a chapter's dialogue against stored profiles, streaming SSE.

        Args:
            chapter_id: The chapter whose dialogue is checked.
            user_id: Authenticated user identifier.

        Yields:
            ``VoiceCheckStreamEvent`` objects: progress, zero or more results,
            then a terminal ``done`` event.

        Raises:
            NotFoundError: If the chapter or its novel does not exist or is
                not accessible.
            ConfigurationError: If no PromptComposer is configured, or the
                per-user routing cascade finds no configured provider
                (ADR-086 lazy resolution — propagates loudly, RULE-11).
        """
        # ADR-086: first-use lazy resolve, post-validation (see ensure_resolved);
        # ahead of the gates — eager-world precedence (L06/L07/L09 landed shape).
        resolved_model = await self.ensure_resolved()

        chapter = await self._chapter_repo.get(chapter_id)
        if chapter is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        novel = await self._novel_repo.get_by_id(chapter.novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(chapter.novel_id))

        composer = self._composer
        if composer is None:
            raise ConfigurationError(
                "PromptComposer is not configured for voice-check analysis.",
                code="NO_COMPOSER",
            )

        language = novel.writing_language or "en"
        parser = self._make_dialogue_parser()
        analyzer = self._make_voice_metrics_analyzer(language)
        utterances = parser.parse(chapter.content or "")
        current_metrics = analyzer.analyze(utterances)
        speaking = sorted(current_metrics.keys())

        if not speaking:
            logger.info(
                "voice_check_no_dialogue",
                feature_id="analysis_voice_check",
                chapter_id=str(chapter_id),
            )
            yield VoiceCheckStreamEvent(
                event="progress",
                progress="No attributed dialogue found in the chapter.",
            )
            yield VoiceCheckStreamEvent(event="done", is_final=True)
            return

        consumer = await self._consumer_provider(chapter.novel_id)
        profiles = await consumer.assemble_for_checking(chapter.novel_id)
        profiles_by_name = {profile.name: profile for profile in profiles}
        checkable = [name for name in speaking if name in profiles_by_name]

        yield VoiceCheckStreamEvent(
            event="progress",
            progress=(
                f"Checking voice consistency for {len(speaking)} speaking "
                f"character(s) ({len(checkable)} with stored profiles)."
            ),
        )

        entries = {}
        if checkable:
            entries = await run_voice_checker_agent(
                utterances=utterances,
                current_metrics=current_metrics,
                profiles_by_name=profiles_by_name,
                checkable=checkable,
                novel=novel,
                chapter=chapter,
                language=language,
                novel_id=chapter.novel_id,
                user_id=user_id,
                model_registry=self._registry,
                model_config=resolved_model.config,
                composer=composer,
                invocation_pipeline=self._invocation_pipeline,
                relationship_repo=self._relationship_repo,
                api_key=resolved_model.api_key,
                base_url=resolved_model.base_url,
            )

        for name in speaking:
            yield VoiceCheckStreamEvent(
                event="result",
                result=assemble_voice_check_result(
                    name=name,
                    profile=profiles_by_name.get(name),
                    entry=entries.get(name),
                    current_metrics=current_metrics,
                ),
            )

        logger.info(
            "voice_check_complete",
            feature_id="analysis_voice_check",
            chapter_id=str(chapter_id),
            speaking=len(speaking),
            checkable=len(checkable),
        )
        yield VoiceCheckStreamEvent(event="done", is_final=True)

    def _make_dialogue_parser(self) -> DialogueParser:
        """Create the reusable deterministic dialogue parser."""
        from narrare_core.analysis.dialogue_parser import DialogueParser

        return DialogueParser()

    def _make_voice_metrics_analyzer(self, language: str) -> VoiceMetricsAnalyzer:
        """Create the reusable deterministic voice-metrics analyzer."""
        from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer

        return VoiceMetricsAnalyzer(language=language)
