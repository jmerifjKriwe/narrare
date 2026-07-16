"""Timeline extraction service — SSE streaming and REST extraction of temporal expressions.

Extracted from ``timeline_analysis_service.py`` to keep service files under
the 300-line limit (RULE-04). Handles the per-chapter extraction of temporal
expressions via ``TemporalExtractionAgent``.

Prompt resolution is Mode 1 (composer-driven) per ADR-054 D2/D7/D8: the
service resolves its system prompt ONCE via
``compose_invocation(composer=..., prompt_context=PromptContext(mode="timeline_extraction"),
intent=LLMIntent.PLAN)``
before the per-chapter loop (the framing does not vary per chapter), then
reuses ``composed_prompt.system`` for each chapter's agent. The per-chapter
content is runtime data (RULE-02a category 3) and flows as the run prompt.

The previous inline f-string feature prompt and the false ADR-048 Mode 2
``_TIMELINE_EXTRACTION_INJECTION`` declaration were removed.
Invocation-composition errors now propagate (RULE-11).

Pattern: Service → PromptComposer (RULE-02) → Core Agent (RULE-01b).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

import structlog

from narrare.planning.timeline_schemas import ExtractedEventResponse
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.models import Chapter
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.planning.timeline_repository import TimelineEventRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class TimelineExtractionService:
    """Service for extracting temporal expressions from chapter content.

    Supports both REST (collect all results) and SSE (stream per-chapter)
    access patterns. Each chapter is processed independently through the
    ``TemporalExtractionAgent`` using the single composed timeline-extraction
    system prompt (Mode 1, ADR-054 D2).

    Args:
        novel_repo: For novel metadata (genre, language).
        chapter_repo: For listing chapters and their summaries.
        model_registry: Shared LLM model registry.
        model_config: Resolved model config (provider + model ID).
        composer: PromptComposer for resolving the governed timeline-extraction
            system prompt via the cascade (RULE-02b / ADR-054 D2). Required for
            ``stream_extraction``.
        event_repo: Optional — for loading existing event names to avoid duplicates.
        invocation_pipeline: Optional pipeline for invocation evidence.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        chapter_repo: ChapterRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig | None = None,
        composer: PromptComposer | None = None,
        event_repo: TimelineEventRepository | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._registry = model_registry
        self._config = model_config
        self._composer = composer
        self._event_repo = event_repo
        self._invocation_pipeline = invocation_pipeline

    async def stream_extraction(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        chapter_ids: list[uuid.UUID] | None,
    ) -> AsyncGenerator[ExtractedEventResponse]:
        """Extract temporal expressions from chapters via SSE streaming.

        Processes chapters one at a time, yielding each extracted expression
        as it becomes available for progressive display in the UI.

        Args:
            novel_id: UUID of the novel.
            user_id: UUID of the requesting user.
            chapter_ids: Optional list of specific chapter IDs. If None,
                processes all chapters.

        Yields:
            ExtractedEventResponse for each temporal expression found.

        Raises:
            NotFoundError: If the novel does not exist.
            ConfigurationError: If no AI provider or PromptComposer is configured.
        """
        from narrare_core.agents.temporal_extraction_agent import (
            TemporalExtractionAgent,
            TemporalExtractionDeps,
        )

        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        if self._config is None:
            raise ConfigurationError(
                "No AI provider configured. Configure one in Settings to use temporal extraction.",
                code="NO_AI_PROVIDER",
            )

        if self._composer is None:
            # Defensive: the factory always wires a composer, but fail loudly
            # (RULE-11) rather than silently falling back to inline assembly.
            raise ConfigurationError(
                "PromptComposer is not configured for timeline extraction.",
                code="NO_COMPOSER",
            )

        chapters = await self._get_chapters(novel_id, chapter_ids)

        # Get existing event names to avoid duplicates
        existing_event_names: list[str] = []
        if self._event_repo is not None:
            existing_events = await self._event_repo.list_by_novel(novel_id)
            existing_event_names = [e.event_name for e in existing_events]

        language = novel.writing_language or "en"

        # Resolve the governed timeline-extraction system prompt ONCE before the
        # per-chapter loop (RULE-02 / ADR-054 D2). The framing does not vary per
        # chapter; only the chapter content (runtime data) does.
        from narrare._app.invocation_context import build_invocation_context
        from narrare_core.ai_invocation import compose_invocation
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.context import PromptContext

        ctx = PromptContext(
            language=language,
            writing_language=language,
            project_title=novel.title,
            genre=novel.genre or "",
            mode="timeline_extraction",
            extra={
                "existing_events": (
                    "\n".join(existing_event_names) if existing_event_names else ""
                ),
            },
        )

        invocation_context = build_invocation_context(
            feature_id="planning_timeline_extraction",
            intent=LLMIntent.PLAN,
            project_id=novel_id,
        )
        invocation = await compose_invocation(
            invocation_pipeline=self._invocation_pipeline,
            invocation_context=invocation_context,
            composer=self._composer,
            prompt_context=ctx,
            intent=LLMIntent.PLAN,
        )
        composed_prompt = invocation.composed_prompt
        # Mode 1 guarantees composed_prompt is set; the guard documents the
        # invariant and satisfies the type-checker (RULE-11: no silent None).
        if composed_prompt is None:  # pragma: no cover - Mode 1 invariant
            raise ConfigurationError(
                "Prompt composition produced no system prompt for timeline extraction.",
                code="COMPOSITION_EMPTY",
            )

        model = await self._registry.get_model(self._config)
        deps = TemporalExtractionDeps(
            genre=novel.genre or "",
            language=language,
            existing_events=existing_event_names,
        )

        for chapter in chapters:
            content = getattr(chapter, "summary", "") or ""
            if not content.strip():
                continue

            try:
                # Reuse the single composed system prompt for every chapter;
                # only the per-chapter content varies (runtime data, user channel).
                agent = TemporalExtractionAgent(model=model, system_prompt=composed_prompt.system)
                chapter_run_prompt = (
                    f"Chapter {getattr(chapter, 'position', 0) + 1}: "
                    f"{getattr(chapter, 'title', '')}\n"
                    f"Content: {content}"
                )
                result = await agent.run(
                    prompt=composed_prompt.user or chapter_run_prompt,
                    deps=deps,
                )

                for expr in result.extracted:
                    response = ExtractedEventResponse(
                        id=f"{chapter.id}_{expr.expression[:20]}",
                        expression=expr.expression,
                        event_name=expr.event_name,
                        timestamp_raw=expr.timestamp_raw,
                        chapter_reference=expr.chapter_reference or getattr(chapter, "title", ""),
                        character_names=expr.character_names,
                        location_name=expr.location_name,
                        confidence=expr.confidence,
                        context=expr.context,
                    )
                    yield response

                # Let the event loop send data between chapters
                await asyncio.sleep(0)

            except Exception:
                # Per-chapter agent failure is logged and skipped so one bad
                # chapter does not abort the stream. This is NOT the RULE-11
                # violation (which was swallowing invocation-COMPOSITION errors
                # above); composition errors now propagate.
                logger.warning(
                    "chapter_extraction_failed",
                    chapter_id=str(getattr(chapter, "id", "unknown")),
                    exc_info=True,
                )
                continue

    async def extract_temporal_expressions(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        chapter_ids: list[uuid.UUID] | None = None,
    ) -> list[ExtractedEventResponse]:
        """Extract temporal expressions (REST variant — collects all results).

        Delegates to ``stream_extraction`` and collects all yielded events
        into a list. This avoids code duplication between REST and SSE paths.

        Args:
            novel_id: UUID of the novel.
            user_id: UUID of the requesting user.
            chapter_ids: Optional list of specific chapter IDs to extract
                from. If None, extracts from all chapters.

        Returns:
            List of extracted temporal expression responses.

        Raises:
            NotFoundError: If the novel does not exist.
            ConfigurationError: If no AI provider is configured.
        """
        results: list[ExtractedEventResponse] = []
        async for event in self.stream_extraction(novel_id, user_id, chapter_ids):
            results.append(event)

        logger.info(
            "temporal_expressions_extracted",
            novel_id=str(novel_id),
            count=len(results),
        )
        return results

    async def _get_chapters(
        self,
        novel_id: uuid.UUID,
        chapter_ids: list[uuid.UUID] | None,
    ) -> list[Chapter]:
        """Load chapters by IDs or all chapters for a novel.

        Args:
            novel_id: UUID of the novel.
            chapter_ids: Optional list of specific chapter IDs. If None,
                returns all chapters.

        Returns:
            List of matching chapters.
        """
        chapters = await self._chapter_repo.list_by_novel(novel_id)
        if chapter_ids is not None:
            chapter_id_set = set(chapter_ids)
            chapters = [ch for ch in chapters if ch.id in chapter_id_set]
        return chapters
