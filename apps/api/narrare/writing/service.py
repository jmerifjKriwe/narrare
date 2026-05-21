"""Writing API service — facade orchestrating generation pipeline and feedback.

This is the main business logic layer for chapter generation.  It delegates:
- DB operations to :class:`GenerationRepository`
- LLM calls to :class:`WritingPipeline` (via gateway — RULE-01)
- Post-processing to :class:`DraftProcessor`
- Feedback recording to :class:`FeedbackCollector`
- Scene operations to :class:`SceneService`
- Stats to :class:`StatsService`
- Tone resolution to :func:`resolve_tone_instructions` (tone_resolver module)

Implements :class:`WritingServiceProtocol` from ``contracts.py`` (RULE-03).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.writing._helpers import record_feedback, validate_generation_input
from narrare.writing.schemas import (
    AcceptResponse,
    GenerateRequest,
    GenerateResponse,
    GenerationStatsResponse,
    RejectResponse,
    SceneNextResponse,
    StopResponse,
)
from narrare.writing.tone_resolver import resolve_tone_instructions
from narrare_core.shared.errors import ConflictError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.settings.custom_tone_service import CustomToneService
    from narrare.writing.models import GenerationRequest
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.scene_service import SceneService
    from narrare.writing.stats_service import StatsService
    from narrare_core.llm.intents import ResolvedModelConfig
    from narrare_core.llm.result import StreamChunk
    from narrare_core.memory.protocols import FeedbackCollector
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)


class WritingService:
    """Orchestrates chapter generation via pipeline + repository (DI, RULE-07)."""

    def __init__(
        self,
        repo: GenerationRepository,
        pipeline: WritingPipeline,
        draft_processor: DraftProcessor,
        config: ResolvedModelConfig,
        api_key: str | None = None,
        base_url: str | None = None,
        feedback_service: FeedbackCollector | None = None,
        scene_service: SceneService | None = None,
        stats_service: StatsService | None = None,
        tone_service: CustomToneService | None = None,
    ) -> None:
        self._repo = repo
        self._pipeline = pipeline
        self._draft_processor = draft_processor
        self._config = config
        self._api_key = api_key
        self._base_url = base_url
        self._feedback = feedback_service
        self._scene_service = scene_service
        self._stats_service = stats_service
        self._tone_service = tone_service

    # -- Generation lifecycle -------------------------------------------

    async def start_generation(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: str,
        request: GenerateRequest,
    ) -> GenerateResponse:
        """Start a generation request. Raises ValidationError or ConflictError."""
        validate_generation_input(request)
        active = await self._repo.get_active_for_chapter(chapter_id)
        if active is not None:
            raise ConflictError(f"Generation already active for chapter {chapter_id}")

        request_id = await self._repo.create(
            chapter_id=chapter_id,
            novel_id=novel_id,
            user_id=UUID(user_id),
            mode=request.mode.value,
            tone=request.tone,
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
        from narrare_core.writing.models import GenerationMode, GenerationRequest

        request_model = await self._get_validated_request(request_id, user_id)
        await self._repo.update_status(
            request_id,
            "streaming",
            started_at=datetime.now(UTC),
            model_id=self._config.model_id,
            provider_name=self._config.provider_name,
        )

        mode = GenerationMode(request_model.mode)
        pipeline_request = GenerationRequest(
            id=request_model.id,
            chapter_id=request_model.chapter_id,
            project_id=request_model.novel_id,
            user_id=request_model.user_id,
            mode=mode,
            tone=request_model.tone,
        )

        custom_tone_instructions = await resolve_tone_instructions(
            tone=request_model.tone,
            user_id=request_model.user_id,
            tone_service=self._tone_service,
        )

        accumulated: list[str] = []
        try:
            async for chunk in self._pipeline.generate(
                pipeline_request,
                config=self._config,
                api_key=self._api_key,
                base_url=self._base_url,
                custom_tone_instructions=custom_tone_instructions,
                **context_kwargs,  # type: ignore[arg-type]
            ):
                if chunk.is_final:
                    raw_text = "".join(accumulated) + chunk.text
                    cleaned = self._draft_processor.process(raw_text)
                    word_count = len(cleaned.split())
                    await self._repo.update_status(
                        request_id,
                        "completed",
                        tokens_used=chunk.usage.total_tokens if chunk.usage else 0,
                        word_count=word_count,
                        completed_at=datetime.now(UTC),
                    )
                    yield chunk
                    return
                accumulated.append(chunk.text)
                yield chunk
        except Exception as e:
            partial = self._draft_processor.process("".join(accumulated), is_partial=True)
            partial_words = len(partial.split()) if partial else 0
            await self._repo.update_status(
                request_id,
                "failed",
                error_message=str(e),
                word_count=partial_words,
                completed_at=datetime.now(UTC),
            )
            logger.error("generation_stream_failed", request_id=str(request_id), error=str(e))

    async def stop_generation(self, request_id: UUID, user_id: str) -> StopResponse:
        """Stop an in-progress generation."""
        request_model = await self._get_validated_request(request_id, user_id)
        await self._pipeline.stop(request_id)
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
        """Accept a generated draft."""
        request_model = await self._get_validated_request(request_id, user_id)
        await record_feedback(self._feedback, request_model, "accept", modified_text=modified_text)
        logger.info("draft_accepted", request_id=str(request_id))

        return AcceptResponse(
            request_id=request_id,
            chapter_id=request_model.chapter_id,
            word_count=request_model.word_count,
        )

    async def reject_draft(self, request_id: UUID, user_id: str) -> RejectResponse:
        """Reject a generated draft."""
        request_model = await self._get_validated_request(request_id, user_id)
        await record_feedback(self._feedback, request_model, "reject")
        logger.info("draft_rejected", request_id=str(request_id))

        return RejectResponse(request_id=request_id)

    # -- Scene-by-scene (delegates to SceneService) ---------------------

    async def next_scene(self, request_id: UUID, user_id: str) -> SceneNextResponse:
        """Request the next scene in scene-by-scene mode."""
        request_model = await self._get_validated_request(request_id, user_id)
        if self._scene_service is not None:
            return await self._scene_service.next_scene(request_model)
        return SceneNextResponse(request_id=request_id, scene_number=1, status=request_model.status)

    async def accept_scene(
        self,
        request_id: UUID,
        scene_number: int,
        user_id: str,
    ) -> AcceptResponse:
        """Accept a specific scene."""
        request_model = await self._get_validated_request(request_id, user_id)
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
        stats = await self._repo.get_stats_for_novel(novel_id)
        return GenerationStatsResponse(
            total_generations=int(stats["total_generations"]),
            success_rate=float(stats["success_rate"]),
            avg_tokens=float(stats["avg_tokens"]),
            avg_word_count=float(stats["avg_word_count"]),
            most_used_model=stats.get("most_used_model"),
        )

    # -- Private helpers ------------------------------------------------

    async def _get_validated_request(
        self,
        request_id: UUID,
        user_id: str,
    ) -> GenerationRequest:
        """Fetch and validate a generation request."""
        request_model = await self._repo.get_by_id(request_id)
        if request_model is None:
            raise NotFoundError("Generation request", identifier=str(request_id))
        if str(request_model.user_id) != user_id:
            raise NotFoundError("Generation request", identifier=str(request_id))
        return request_model
