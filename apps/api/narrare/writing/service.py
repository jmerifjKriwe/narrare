"""Writing API service — facade orchestrating generation pipeline and feedback.

This is the main business logic layer for chapter generation.  It delegates:
- DB operations to :class:`GenerationRepository`
- LLM calls to :class:`WritingPipeline` (via gateway — RULE-01b)
- Post-processing to :class:`DraftProcessor`; feedback to :class:`FeedbackCollector`
- Stream iteration/finalization to :func:`stream_pipeline_chunks` (``_stream_service``)
- Context assembly (tone / KB / session memory / series history / novel
  supply) to :func:`build_stream_inputs` (``_writing_support``)
- Scene operations to :class:`SceneService`; stats to :class:`StatsService`

Model acquisition is LAZY (ADR-086, M-budget): the factory wires a
``LazyModelResolution`` plus a deferred runtime composition; the service
resolves at first use — :meth:`ensure_resolved` at the end of
:meth:`validate_request_access` (the router's pre-stream seam) and via
``stream_generation`` for direct callers — so gates stay ahead of the
cascades and an unconfigured provider surfaces as a loud pre-header 400.

Implements :class:`WritingServiceProtocol` from ``contracts.py`` (RULE-03).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import structlog

from narrare.writing._draft_feedback import accept_draft_request, reject_draft_request
from narrare.writing._helpers import (
    get_validated_request,
    start_generation_request,
)
from narrare.writing._pipeline_request_support import build_pipeline_request
from narrare.writing._stream_service import stream_pipeline_chunks
from narrare.writing._writing_support import (
    WritingRuntime,
    build_generation_stats_response,
    build_stream_inputs,
)
from narrare.writing.schemas import (
    AcceptResponse,
    GenerateRequest,
    GenerateResponse,
    GenerationStatsResponse,
    RejectResponse,
    SceneNextResponse,
    StopResponse,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable
    from uuid import UUID

    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.novels.repository import NovelRepository
    from narrare.series.series_history_provider import SeriesHistoryProvider
    from narrare.settings.custom_tone_service import CustomToneService
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.scene_service import SceneService
    from narrare.writing.stats_service import StatsService
    from narrare_core.llm.result import StreamChunk
    from narrare_core.memory.protocols import FeedbackCollector, SessionMemoryCollector
    from narrare_core.writing.draft_processor import DraftProcessor

logger = structlog.get_logger(__name__)


class WritingService:
    """Orchestrates chapter generation via pipeline + repository (DI, RULE-07).

    Args:
        repo: Generation request repository (status lifecycle + rows).
        runtime_factory: Zero-arg async callable returning the
            :class:`WritingRuntime` — deferred composition over both
            cascades (ADR-086: first use only, never construction).
    """

    def __init__(
        self,
        repo: GenerationRepository,
        runtime_factory: Callable[[], Awaitable[WritingRuntime]],
        draft_processor: DraftProcessor,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        feedback_service: FeedbackCollector | None = None,
        scene_service: SceneService | None = None,
        stats_service: StatsService | None = None,
        tone_service: CustomToneService | None = None,
        relationship_repo: RelationshipRepository | None = None,
        session_memory: SessionMemoryCollector | None = None,
        series_history_provider: SeriesHistoryProvider | None = None,
    ) -> None:
        self._repo = repo
        self._runtime_factory = runtime_factory
        self._runtime: WritingRuntime | None = None
        self._draft_processor = draft_processor
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._feedback = feedback_service
        self._scene_service = scene_service
        self._stats_service = stats_service
        self._tone_service = tone_service
        self._relationship_repo = relationship_repo
        self._session_memory = session_memory
        self._series_history_provider = series_history_provider

    # -- Lazy runtime (ADR-086) -------------------------------------------

    async def ensure_resolved(self) -> WritingRuntime:
        """Compose the effective writing runtime at first use; idempotent.

        Runs the deferred composition — both cascades, the sampling
        overrides, the ADR-082 budgets, the tier-wired pipeline — exactly
        once, cached.  Errors propagate uncached (RULE-11):
        ``ConfigurationError`` surfaces as a pre-header 400 (SSE).
        """
        if self._runtime is None:
            self._runtime = await self._runtime_factory()
        return self._runtime

    # -- Generation lifecycle -------------------------------------------

    async def start_generation(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: str,
        request: GenerateRequest,
    ) -> GenerateResponse:
        """Start a generation request. Raises NotFoundError (IDOR gate
        precedes row creation), ValidationError or ConflictError."""
        request_id = await start_generation_request(
            self._repo,
            self._chapter_repo,
            self._novel_repo,
            chapter_id,
            novel_id,
            user_id,
            request,
        )
        logger.info(
            "generation_started",
            request_id=str(request_id),
            chapter_id=str(chapter_id),
            mode=request.mode.value,
            tone=request.tone,
        )
        return GenerateResponse(
            request_id=request_id,
            status="pending",
            mode=request.mode.value,
        )

    async def stream_generation(
        self,
        request_id: UUID,
        user_id: str,
        **context_kwargs: object,
    ) -> AsyncIterator[StreamChunk]:
        """Stream generated text chunks for an existing request."""
        from narrare_core.writing._enums import GenerationMode

        request_model = await get_validated_request(self._repo, request_id, user_id)
        # ADR-086 L37: first-use lazy runtime (idempotent; post-gate).
        runtime = await self.ensure_resolved()
        await self._repo.update_status(
            request_id,
            "streaming",
            started_at=datetime.now(UTC),
            model_id=runtime.config.model_id,
            provider_name=runtime.config.provider_name,
        )

        mode = GenerationMode(request_model.mode)
        pipeline_request = build_pipeline_request(request_model, mode)

        # Context + novel supply (RULE-04 builder; cascade-output budget).
        inputs = await build_stream_inputs(
            request_model,
            tone_service=self._tone_service,
            relationship_repo=self._relationship_repo,
            session_memory=self._session_memory,
            series_history_provider=self._series_history_provider,
            series_history_budget=runtime.series_history_budget,
            novel_repo=self._novel_repo,
            user_id=user_id,
        )

        # Stream the pipeline and finalize the request row (RULE-04
        # extraction — iteration mechanics live in ``_stream_service``).
        async for chunk in stream_pipeline_chunks(
            repo=self._repo,
            pipeline=runtime.pipeline,
            draft_processor=self._draft_processor,
            session_memory=self._session_memory,
            request_model=request_model,
            request_id=request_id,
            mode=mode,
            pipeline_request=pipeline_request,
            config=runtime.config,
            api_key=runtime.api_key,
            base_url=runtime.base_url,
            custom_tone_instructions=inputs.custom_tone_instructions,
            kb_relationships=inputs.kb_relationships,
            cross_session_context=inputs.cross_session_context,
            series_history=inputs.series_history,
            project_title=inputs.project_title,
            genre=inputs.genre,
            context_kwargs=cast("dict[str, Any]", context_kwargs),
        ):
            yield chunk

    async def stop_generation(self, request_id: UUID, user_id: str) -> StopResponse:
        """Stop an in-progress generation."""
        request_model = await get_validated_request(self._repo, request_id, user_id)
        # ADR-086 L37: the pipeline is a cascade-composed runtime member.
        runtime = await self.ensure_resolved()
        await runtime.pipeline.stop(request_id)
        word_count = request_model.word_count
        await self._repo.update_status(request_id, "stopped", completed_at=datetime.now(UTC))
        logger.info("generation_stopped", request_id=str(request_id), word_count=word_count)
        return StopResponse(request_id=request_id, word_count=word_count)

    # -- Draft accept / reject ------------------------------------------

    async def accept_draft(
        self,
        request_id: UUID,
        user_id: str,
        modified_text: str | None = None,
    ) -> AcceptResponse:
        """Accept a generated draft.

        Delegates per RULE-04; raises ``EMPTY_DRAFT`` for text-less rows
        (see :func:`narrare.writing._draft_feedback.accept_draft_request`).
        """
        return await accept_draft_request(
            self._repo, self._feedback, request_id, user_id, modified_text
        )

    async def reject_draft(self, request_id: UUID, user_id: str) -> RejectResponse:
        """Reject a generated draft."""
        return await reject_draft_request(self._repo, self._feedback, request_id, user_id)

    # -- Scene-by-scene (delegates to SceneService) ---------------------

    async def next_scene(self, request_id: UUID, user_id: str) -> SceneNextResponse:
        """Request the next scene in scene-by-scene mode."""
        request_model = await get_validated_request(self._repo, request_id, user_id)
        if self._scene_service is not None:
            return await self._scene_service.next_scene(request_model)
        return SceneNextResponse(request_id=request_id, scene_number=1, status=request_model.status)

    async def accept_scene(
        self, request_id: UUID, scene_number: int, user_id: str
    ) -> AcceptResponse:
        """Accept a specific scene."""
        request_model = await get_validated_request(self._repo, request_id, user_id)
        if self._scene_service is not None:
            return await self._scene_service.accept_scene(request_model, scene_number)
        return AcceptResponse(
            request_id=request_id,
            chapter_id=request_model.chapter_id,
            word_count=request_model.word_count,
        )

    # -- Stats (delegates to StatsService) ------------------------------

    async def get_stats(self, novel_id: UUID, user_id: str) -> GenerationStatsResponse:
        """Aggregate generation statistics for a novel."""
        if self._stats_service is not None:
            return await self._stats_service.get_stats(novel_id)
        return build_generation_stats_response(await self._repo.get_stats_for_novel(novel_id))

    async def validate_request_access(
        self,
        request_id: UUID,
        user_id: str,
    ) -> None:
        """Validate that a generation request exists and belongs to the user.

        Raises NotFoundError if not found or access denied.
        Used by router to validate before starting SSE response.

        Raises:
            narrare_core.shared.errors.ConfigurationError: If the user
                has no AI provider configured (first-use composition).
        """
        await get_validated_request(self._repo, request_id, user_id)
        # ADR-086 L37: first-use composition — post-IDOR-gate and
        # pre-SSE-headers — so an unconfigured provider stays a loud
        # pre-header 400 (RULE-11), never a preempting factory error.
        await self.ensure_resolved()
