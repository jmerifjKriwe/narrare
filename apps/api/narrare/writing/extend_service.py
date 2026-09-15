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

from narrare.writing._extend_support import build_extend_stream_inputs, mark_extend_failed
from narrare.writing._helpers import create_request_row, verify_chapter_access
from narrare.writing.schemas import ExtendLength, ExtendRequest, GenerateResponse
from narrare_core.shared.errors import ConflictError, ValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.novels.repository import NovelRepository
    from narrare.settings.custom_tone_service import CustomToneService
    from narrare.writing._extend_support import ExtendRuntime
    from narrare.writing.repository import GenerationRepository
    from narrare_core.llm.result import StreamChunk
    from narrare_core.writing.draft_processor import DraftProcessor

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
        runtime_factory: Callable[[], Awaitable[ExtendRuntime]],
        draft_processor: DraftProcessor,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        tone_service: CustomToneService | None = None,
        relationship_repo: RelationshipRepository | None = None,
    ) -> None:
        self._repo = repo
        self._runtime_factory = runtime_factory
        self._runtime: ExtendRuntime | None = None
        self._draft_processor = draft_processor
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._tone_service = tone_service
        self._relationship_repo = relationship_repo

    # -- Lazy runtime (ADR-086) --------------------------------------------

    async def ensure_resolved(self) -> ExtendRuntime:
        """Compose the effective extend runtime at first use; idempotent.

        Invokes the factory's deferred composition — the EXTEND routing
        cascade AND the token-limits cascade, the sampling overrides,
        the ADR-082 budgets, and the tier-wired pipeline — exactly once;
        the frozen result is cached for the service's lifetime.  Errors
        propagate uncached (RULE-11): ``ConfigurationError``
        (``NO_AI_PROVIDER``) surfaces as a pre-header 400 on this SSE
        endpoint.
        """
        if self._runtime is None:
            self._runtime = await self._runtime_factory()
        return self._runtime

    # -- Public API --------------------------------------------------------

    async def validate_extend(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        request: ExtendRequest,
        *,
        user_id: str,
    ) -> None:
        """Pre-validate extend request before starting SSE response.

        Called by the router BEFORE creating the StreamingResponse to
        ensure validation errors (422, 409, 404) are returned with proper
        HTTP status codes instead of causing RuntimeError after headers
        are sent.

        Ownership gate (IDOR remediation S6): the S5 helper
        :func:`verify_chapter_access` runs FIRST — foreign and unknown
        chapter ids are indistinguishable 404s raised before any input
        validation, active-generation check, or request-row creation.
        The lazy runtime composition (ADR-086) runs LAST — after all
        gates — so gate failures keep precedence over an unconfigured
        provider's 400, and that 400 itself still fires before any SSE
        headers are sent.

        Raises:
            NotFoundError: If the chapter does not exist, does not belong
                to the addressed novel, or the novel belongs to another
                user.
            ValidationError: If text_before is empty.
            ConflictError: If another generation is active for the chapter.
            narrare_core.shared.errors.ConfigurationError: If the user
                has no AI provider configured (first-use composition).
        """
        await verify_chapter_access(
            self._chapter_repo, self._novel_repo, chapter_id, novel_id, user_id
        )

        if not request.text_before.strip():
            raise ValidationError(
                "text_before must not be empty",
                code="MISSING_INPUT",
            )

        active = await self._repo.get_active_for_chapter(chapter_id)
        if active is not None:
            raise ConflictError(f"Generation already active for chapter {chapter_id}")

        # ADR-086 L32: first-use lazy composition of BOTH cascades
        # (routing + token limits, incl. the tier-wired pipeline) —
        # post-validation and post-gate — so an unconfigured provider
        # stays a loud pre-header 400 (RULE-11), never a preempting
        # factory-time error.
        await self.ensure_resolved()

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
        await self.validate_extend(chapter_id, novel_id, request, user_id=user_id)
        request_id = await create_request_row(
            self._repo, chapter_id, novel_id, user_id, "extend", request.tone
        )

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

        # Step 2: Transition to streaming.  The runtime is already
        # composed (ADR-086): the pre-stream validate_extend — called by
        # start_extend below — ran the first-use composition on this
        # service instance, so ensure_resolved here is a cached read.
        runtime = await self.ensure_resolved()
        await self._repo.update_status(
            request_id,
            "streaming",
            started_at=datetime.now(UTC),
            model_id=runtime.config.model_id,
            provider_name=runtime.config.provider_name,
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

        # Steps 4-5b: prompt inputs — content block with the continuation
        # marker, resolved custom tone instructions, and the formatted KB
        # relationships (FIND-009); extracted to _extend_support (RULE-04).
        stream_inputs = await build_extend_stream_inputs(
            request=request,
            user_id=UUID(user_id),
            tone_service=self._tone_service,
            relationship_repo=self._relationship_repo,
            novel_id=novel_id,
        )

        # Step 6: Stream via pipeline (RULE-01b, RULE-02).
        accumulated: list[str] = []
        try:
            async for chunk in runtime.pipeline.generate(
                pipeline_request,
                config=runtime.config,
                api_key=runtime.api_key,
                base_url=runtime.base_url,
                chapter_content=stream_inputs.chapter_content,
                custom_tone_instructions=stream_inputs.custom_tone_instructions,
                kb_relationships=stream_inputs.kb_relationships,
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
            await mark_extend_failed(
                self._repo,
                self._draft_processor,
                request_id,
                accumulated,
                e,
            )
