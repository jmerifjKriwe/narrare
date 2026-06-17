"""Extend chapter service — SSE-direct extend generation.

Creates a ``generation_request`` row and streams the extension in one
method call.  The frontend receives SSE events directly from
``POST /extend`` — no separate ``GET /stream`` call needed.

Follows the same pattern as :class:`InlineSuggestService` (separate
service class per RULE-04: WritingService is at its 300-line limit).

Implements :class:`ExtendServiceProtocol` from ``contracts.py`` (RULE-03).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError

from narrare.writing.schemas import ExtendLength, ExtendRequest, GenerateResponse
from narrare.writing.tone_resolver import resolve_tone_instructions
from narrare_core.shared.errors import ConflictError, NotFoundError, ValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.settings.custom_tone_service import CustomToneService
    from narrare.writing.repository import GenerationRepository
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.result import StreamChunk
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)

# ExtendLength → word_target mapping (spec: short~150, medium~400, long~750).
_EXTEND_WORD_TARGETS: dict[ExtendLength, int] = {
    ExtendLength.SHORT: 150,
    ExtendLength.MEDIUM: 400,
    ExtendLength.LONG: 750,
}


class ExtendService:
    """Orchestrates chapter extension via pipeline + repository (DI, RULE-07).

    Uses the SSE-direct pattern: ``stream_extend()`` creates the request
    row AND streams the result.  The frontend receives SSE events directly.
    Accept/reject endpoints from the main writing router still work because
    they key off the ``generation_request.id`` included in the final SSE event.
    """

    def __init__(
        self,
        repo: GenerationRepository,
        pipeline: WritingPipeline,
        draft_processor: DraftProcessor,
        config: ResolvedModelConfig,
        api_key: str | None = None,
        base_url: str | None = None,
        tone_service: CustomToneService | None = None,
        relationship_repo: RelationshipRepository | None = None,
    ) -> None:
        self._repo = repo
        self._pipeline = pipeline
        self._draft_processor = draft_processor
        self._config = config
        self._api_key = api_key
        self._base_url = base_url
        self._tone_service = tone_service
        self._relationship_repo = relationship_repo

    # -- Public API --------------------------------------------------------

    async def validate_extend(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        request: ExtendRequest,
    ) -> None:
        """Pre-validate extend request before starting SSE response.

        Called by the router BEFORE creating the StreamingResponse to
        ensure validation errors (422, 409, 404) are returned with proper
        HTTP status codes instead of causing RuntimeError after headers
        are sent.

        Raises:
            ValidationError: If text_before is empty.
            ConflictError: If another generation is active for the chapter.
            NotFoundError: If the chapter or novel does not exist.
        """
        if not request.text_before.strip():
            raise ValidationError(
                "text_before must not be empty",
                code="MISSING_INPUT",
            )

        if not await self._repo.chapter_exists(chapter_id):
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        active = await self._repo.get_active_for_chapter(chapter_id)
        if active is not None:
            raise ConflictError(f"Generation already active for chapter {chapter_id}")

    async def start_extend(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: str,
        request: ExtendRequest,
    ) -> GenerateResponse:
        """Validate and create an extend generation request.

        Args:
            chapter_id: Chapter to extend.
            novel_id: Novel the chapter belongs to.
            user_id: Authenticated user identifier.
            request: Extend-specific parameters (text_before, length, etc.).

        Returns:
            GenerateResponse with status "pending".

        Raises:
            ValidationError: If text_before is empty.
            ConflictError: If another generation is active for the chapter.
            NotFoundError: If the chapter or novel does not exist.
        """
        await self.validate_extend(chapter_id, novel_id, request)

        try:
            request_id = await self._repo.create_if_no_active(
                chapter_id=chapter_id,
                novel_id=novel_id,
                user_id=UUID(user_id),
                mode="extend",
                tone=request.tone,
            )
        except IntegrityError as exc:
            raise NotFoundError("Chapter or Novel", identifier=str(chapter_id)) from exc

        logger.info(
            "extend_started",
            request_id=str(request_id),
            chapter_id=str(chapter_id),
            length=request.length.value,
        )

        return GenerateResponse(
            request_id=request_id,
            status="pending",
            mode="extend",
        )

    async def stream_extend(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: str,
        request: ExtendRequest,
    ) -> AsyncIterator[StreamChunk]:
        """Create request row AND stream extend generation (SSE-direct).

        Internally calls ``start_extend()`` first, then streams the
        generated continuation through the pipeline.  Handles status
        transitions (pending → streaming → completed/failed) and
        draft post-processing.

        Args:
            chapter_id: Chapter to extend.
            novel_id: Novel the chapter belongs to.
            user_id: Authenticated user identifier.
            request: Extend-specific parameters.

        Yields:
            StreamChunk instances with incremental text.
        """
        from narrare_core.writing._enums import GenerationMode
        from narrare_core.writing.models import (
            GenerationRequest as CoreGenerationRequest,
        )

        # Step 1: Create the request row (validates input + checks concurrency).
        response = await self.start_extend(chapter_id, novel_id, user_id, request)
        request_id = response.request_id

        # Step 2: Transition to streaming.
        await self._repo.update_status(
            request_id,
            "streaming",
            started_at=datetime.now(UTC),
            model_id=self._config.model_id,
            provider_name=self._config.provider_name,
        )

        # Step 3: Build pipeline request with extend-specific parameters.
        word_target = _EXTEND_WORD_TARGETS[request.length]
        pipeline_request = CoreGenerationRequest(
            id=request_id,
            chapter_id=chapter_id,
            project_id=novel_id,
            user_id=UUID(user_id),
            mode=GenerationMode.EXTEND,
            tone=request.tone,
            word_target=word_target,
            writing_language=request.language,
        )

        # Step 4: Build chapter_content for extend: pre-text + marker + post-text.
        chapter_content = request.text_before
        if request.text_after:
            chapter_content += "\n[CONTINUE FROM HERE]\n" + request.text_after
        else:
            chapter_content += "\n[CONTINUE FROM HERE]\n"

        # Step 5: Resolve custom tone instructions.
        custom_tone_instructions = await resolve_tone_instructions(
            tone=request.tone,
            user_id=UUID(user_id),
            tone_service=self._tone_service,
        )

        # Step 5b: Fetch and format KB relationships for prompt context (FIND-009)
        from narrare.writing._relationship_helpers import fetch_formatted_relationships

        kb_relationships = await fetch_formatted_relationships(
            self._relationship_repo,
            novel_id,
        )

        # Step 6: Stream via pipeline (RULE-01b, RULE-02).
        accumulated: list[str] = []
        try:
            async for chunk in self._pipeline.generate(
                pipeline_request,
                config=self._config,
                api_key=self._api_key,
                base_url=self._base_url,
                chapter_content=chapter_content,
                custom_tone_instructions=custom_tone_instructions,
                kb_relationships=kb_relationships,
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
            partial = self._draft_processor.process(
                "".join(accumulated),
                is_partial=True,
            )
            partial_words = len(partial.split()) if partial else 0
            await self._repo.update_status(
                request_id,
                "failed",
                error_message=str(e),
                word_count=partial_words,
                completed_at=datetime.now(UTC),
            )
            logger.error(
                "extend_stream_failed",
                request_id=str(request_id),
                error=str(e),
            )
