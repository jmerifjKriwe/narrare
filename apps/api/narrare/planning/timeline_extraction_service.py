"""Timeline extraction service — SSE streaming and REST extraction of temporal expressions.

Extracted from ``timeline_analysis_service.py`` to keep service files under
the 300-line limit (RULE-04). Handles the per-chapter extraction of temporal
expressions via ``TemporalExtractionAgent``.

Prompt resolution is Mode 1 (composer-driven) per ADR-054 D2/D7/D8: the
composed prompt and the prepared agent are acquired ONCE via
:func:`narrare.planning._timeline_extraction_support.prepare_extraction_invocation`
before the per-chapter loop (the framing does not vary per chapter), then
the loop reuses ``composed_prompt.system`` for each chapter's agent. The
per-chapter content is runtime data (RULE-02a category 3) and flows as
the run prompt.

The previous inline f-string feature prompt and the false ADR-048 Mode 2
``_TIMELINE_EXTRACTION_INJECTION`` declaration were removed.
Invocation-composition errors now propagate (RULE-11).

Since ADR-086 L24 model routing is consumed lazily: the per-user PLAN
cascade resolves on first use (``ensure_resolved`` — after the uid-scoped
novel guard, per the planning guard ruling), and the eager factory's
wiring-time ``except ConfigurationError`` swallow is entry-point policy
(``no_ai_provider_configured`` log + the preserved ``NO_AI_PROVIDER``
raise).

Pattern: Service → PromptComposer (RULE-02) → Core Agent (RULE-01b).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from narrare.planning._timeline_extraction_helpers import load_chapters
from narrare.planning._timeline_extraction_support import prepare_extraction_invocation
from narrare.planning.timeline_schemas import ExtractedEventResponse
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    import uuid
    from collections.abc import AsyncGenerator

    from narrare._app.dependencies_services import ModelResolution
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
        model_resolution: Lazy per-user model resolution (ADR-086 L24) —
            the PLAN routing cascade resolves on first use, never at
            construction. A ``ConfigurationError`` (no AI provider) is
            degraded at the entry point (AI-optional policy).
        composer: PromptComposer for resolving the governed timeline-extraction
            system prompt via the cascade (RULE-02b / ADR-054 D2). Required for
            ``stream_extraction``.
        event_repo: Optional — for loading existing event names to avoid duplicates.
        invocation_pipeline: Optional pipeline for invocation evidence.
        run_limit_resolver: Optional ADR-045 run-limit resolver; defaults to
            ``DefaultRunLimitResolver`` (Task 3 wiring).
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        chapter_repo: ChapterRepository,
        model_registry: ModelRegistry,
        model_resolution: ModelResolution,
        composer: PromptComposer | None = None,
        event_repo: TimelineEventRepository | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._registry = model_registry
        self._model_resolution = model_resolution
        # Resolved triple — unset until first use; a failed (graceful)
        # resolve leaves it unset for the instance's lifetime.
        self._config: ResolvedModelConfig | None = None
        self._api_key: str | None = None
        self._base_url: str | None = None
        self._resolve_attempted = False
        self._composer = composer
        self._event_repo = event_repo
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

    async def ensure_resolved(self) -> None:
        """Resolve the per-user PLAN routing cascade once (ADR-086 L24).

        First call awaits the injected ``ModelResolution`` and caches the
        resolved triple into ``_config``/``_api_key``/``_base_url``; repeat
        calls are idempotent — the cascade runs at most once per instance,
        success or failure (eager-world timing also resolved exactly once
        per request). ``ConfigurationError`` propagates UNCHANGED: the
        graceful swallow is entry-point policy (see :meth:`stream_extraction`),
        so this method stays honest about what happened (RULE-11).
        """
        if self._resolve_attempted:
            return
        self._resolve_attempted = True
        resolved = await self._model_resolution.resolve()
        self._config = resolved.config
        self._api_key = resolved.api_key
        self._base_url = resolved.base_url

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
            ConfigurationError: If no AI provider is configured (the
                preserved degraded outcome; ADR-086 L24 graceful entry
                policy), the PromptComposer is missing, or prompt
                composition fails (RULE-11).
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        # ADR-086 L24: first-use lazy resolve — the uid-scoped novel guard
        # above stays ahead of the cascade (eager-world precedence; the
        # ADR-086 planning guard ruling). Degradation is entry-point
        # policy: a missing AI provider is logged (the eager factory's
        # event, byte-identical) and leaves the triple unset, so the
        # preserved ``NO_AI_PROVIDER`` outcome below fires exactly as it
        # did when the eager factory swallowed this error at wiring time —
        # timing only. The resolve is attempted at most once per instance.
        try:
            await self.ensure_resolved()
        except ConfigurationError:
            logger.info("no_ai_provider_configured", novel_id=str(novel_id))

        # Guard: no AI provider configured — cannot extract
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

        chapters = await load_chapters(self._chapter_repo, novel_id, chapter_ids)

        # Get existing event names to avoid duplicates
        existing_event_names: list[str] = []
        if self._event_repo is not None:
            existing_events = await self._event_repo.list_by_novel(novel_id)
            existing_event_names = [e.event_name for e in existing_events]

        language = novel.writing_language or "en"

        # Prompt acquisition + agent assembly (Mode 1 composition, Task 6b
        # prepare assembly point, one agent for the whole loop) — extracted
        # to ``_timeline_extraction_support.py`` (RULE-04 split, ADR-086 L24).
        invocation = await prepare_extraction_invocation(
            composer=self._composer,
            invocation_pipeline=self._invocation_pipeline,
            registry=self._registry,
            config=self._config,
            api_key=self._api_key,
            base_url=self._base_url,
            run_limit_resolver=self._run_limit_resolver,
            novel=novel,
            novel_id=novel_id,
            language=language,
            existing_event_names=existing_event_names,
        )

        for chapter in chapters:
            content = getattr(chapter, "summary", "") or ""
            if not content.strip():
                continue

            try:
                # Reuse the single composed system prompt for every chapter;
                # only the per-chapter content varies (runtime data, user channel).
                chapter_run_prompt = (
                    f"Chapter {getattr(chapter, 'position', 0) + 1}: "
                    f"{getattr(chapter, 'title', '')}\n"
                    f"Content: {content}"
                )
                result = await invocation.agent.run(
                    prompt=invocation.composed_prompt.user or chapter_run_prompt,
                    deps=invocation.deps,
                    model_settings=invocation.prepared.model_settings,
                    usage_limits=invocation.prepared.usage_limits,
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
