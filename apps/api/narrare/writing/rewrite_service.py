"""Rewrite selection service — SSE-direct rewrite generation.

Creates a ``generation_request`` row and streams rewrite alternatives
in one method call.  The frontend receives SSE events directly from
``POST /rewrite`` — no separate ``GET /stream`` call needed.

Follows the same pattern as :class:`ExtendService` (separate service
class per RULE-04: WritingService is at its 300-line limit).

Implements :class:`RewriteServiceProtocol` from ``contracts_rewrite.py``
(RULE-03).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.writing._helpers import create_request_row, verify_chapter_access
from narrare.writing.schemas import GenerateResponse
from narrare.writing.tone_resolver import resolve_tone_instructions
from narrare_core.shared.errors import ConflictError, ValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.novels.repository import NovelRepository
    from narrare.settings.custom_tone_service import CustomToneService
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.schemas_rewrite import RewriteRequest
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.result import StreamChunk
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)


class RewriteService:
    """Orchestrates selection rewriting via pipeline + repository (DI, RULE-07).

    Uses the SSE-direct pattern: ``stream_rewrite()`` creates the request
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
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        api_key: str | None = None,
        base_url: str | None = None,
        tone_service: CustomToneService | None = None,
        relationship_repo: RelationshipRepository | None = None,
    ) -> None:
        self._repo = repo
        self._pipeline = pipeline
        self._draft_processor = draft_processor
        self._config = config
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._api_key = api_key
        self._base_url = base_url
        self._tone_service = tone_service
        self._relationship_repo = relationship_repo

    # -- Public API --------------------------------------------------------

    async def validate_rewrite(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        request: RewriteRequest,
        *,
        user_id: str,
    ) -> None:
        """Pre-validate rewrite request before starting SSE response.

        Called by the router BEFORE creating the StreamingResponse to
        ensure validation errors (422, 409, 404) are returned with proper
        HTTP status codes instead of causing RuntimeError after headers
        are sent.

        Ownership gate (IDOR S6): ``verify_chapter_access`` runs FIRST —
        foreign ≡ unknown 404s precede input validation, the conflict
        check, and any request-row creation.

        Raises:
            NotFoundError: Chapter unknown, not in the addressed novel,
                or novel owned by another user.
            ValidationError: If selection_text is empty.
            ConflictError: If another generation is active for the chapter.
        """
        await verify_chapter_access(
            self._chapter_repo, self._novel_repo, chapter_id, novel_id, user_id
        )

        if not request.selection_text.strip():
            raise ValidationError(
                "selection_text must not be empty",
                code="MISSING_INPUT",
            )

        active = await self._repo.get_active_for_chapter(chapter_id)
        if active is not None:
            raise ConflictError(f"Generation already active for chapter {chapter_id}")

    async def start_rewrite(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: str,
        request: RewriteRequest,
    ) -> GenerateResponse:
        """Validate and create a rewrite generation request.

        Args:
            chapter_id: Chapter containing the selection to rewrite.
            novel_id: Novel the chapter belongs to.
            user_id: Authenticated user identifier.
            request: Rewrite-specific parameters (selection_text, mode, etc.).

        Returns:
            GenerateResponse with status "pending".

        Raises:
            ValidationError: If selection_text is empty.
            ConflictError: If another generation is active for the chapter.
            NotFoundError: If the chapter or novel does not exist.
        """
        await self.validate_rewrite(chapter_id, novel_id, request, user_id=user_id)
        request_id = await create_request_row(
            self._repo, chapter_id, novel_id, user_id, "rewrite", request.tone
        )

        logger.info(
            "rewrite_started",
            request_id=str(request_id),
            chapter_id=str(chapter_id),
            mode=request.mode.value,
        )

        return GenerateResponse(
            request_id=request_id,
            status="pending",
            mode="rewrite",
        )

    async def stream_rewrite(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: str,
        request: RewriteRequest,
    ) -> AsyncIterator[StreamChunk]:
        """Create request row AND stream rewrite generation (SSE-direct).

        Internally calls ``start_rewrite()`` first, then streams the
        rewritten alternatives through the pipeline.  Handles status
        transitions (pending → streaming → completed/failed) and
        draft post-processing.

        Args:
            chapter_id: Chapter containing the selection to rewrite.
            novel_id: Novel the chapter belongs to.
            user_id: Authenticated user identifier.
            request: Rewrite-specific parameters.

        Yields:
            StreamChunk instances with incremental text.
        """
        from narrare_core.writing._enums import GenerationMode
        from narrare_core.writing.models import (
            GenerationRequest as CoreGenerationRequest,
        )

        # Step 1: Create the request row (validates input + checks concurrency).
        response = await self.start_rewrite(chapter_id, novel_id, user_id, request)
        request_id = response.request_id

        # Step 2: Transition to streaming.
        await self._repo.update_status(
            request_id,
            "streaming",
            started_at=datetime.now(UTC),
            model_id=self._config.model_id,
            provider_name=self._config.provider_name,
        )

        # Step 3: Build pipeline request with rewrite-specific parameters.
        pipeline_request = CoreGenerationRequest(
            id=request_id,
            chapter_id=chapter_id,
            project_id=novel_id,
            user_id=UUID(user_id),
            mode=GenerationMode.REWRITE,
            tone=request.tone,
            word_target=0,  # Rewrite doesn't use word targets
            writing_language=request.language,
        )

        # Step 4: Build chapter_content for rewrite: the selection text is
        # the primary content.  Context markers provide surrounding text.
        chapter_content = request.selection_text
        if request.context_before or request.context_after:
            parts: list[str] = []
            if request.context_before:
                parts.append(request.context_before)
            parts.append("[SELECTION START]")
            parts.append(request.selection_text)
            parts.append("[SELECTION END]")
            if request.context_after:
                parts.append(request.context_after)
            chapter_content = "\n".join(parts)

        # Step 5: Resolve custom tone instructions.
        custom_tone_instructions = await resolve_tone_instructions(
            tone=request.tone,
            user_id=UUID(user_id),
            tone_service=self._tone_service,
        )

        # Step 6: Determine rewrite mode and custom instructions.
        rewrite_mode = request.mode.value
        custom_instructions = request.custom_instructions or ""

        # Step 6b: Fetch and format KB relationships for prompt context (FIND-009)
        from narrare.writing._relationship_helpers import fetch_formatted_relationships

        kb_relationships = await fetch_formatted_relationships(
            self._relationship_repo,
            novel_id,
        )

        # Step 7: Stream via pipeline (RULE-01b, RULE-02).
        accumulated: list[str] = []
        try:
            async for chunk in self._pipeline.generate(
                pipeline_request,
                config=self._config,
                api_key=self._api_key,
                base_url=self._base_url,
                chapter_content=chapter_content,
                custom_tone_instructions=custom_tone_instructions,
                selection_text=request.selection_text,
                context_before=request.context_before or "",
                context_after=request.context_after or "",
                rewrite_mode=rewrite_mode,
                custom_instructions=custom_instructions,
                rewrite_count=request.count,
                kb_relationships=kb_relationships.text,
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
                "rewrite_stream_failed",
                request_id=str(request_id),
                error=str(e),
            )
