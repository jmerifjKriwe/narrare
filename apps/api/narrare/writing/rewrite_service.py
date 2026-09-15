"""Rewrite selection service — SSE-direct rewrite generation.

Creates a ``generation_request`` row and streams rewrite alternatives
in one method call.  The frontend receives SSE events directly from
``POST /rewrite`` — no separate ``GET /stream`` call needed.

Follows the same pattern as :class:`ExtendService` (separate service
class per RULE-04: WritingService is at its 300-line limit).

Implements :class:`RewriteServiceProtocol` from ``contracts_rewrite.py``
(RULE-03).

Model acquisition is LAZY (ADR-086, M-budget): the factory wires a
``LazyModelResolution`` plus a deferred runtime composition; the service
resolves at first use — :meth:`ensure_resolved` at the end of
:meth:`validate_rewrite` (the router's pre-stream seam) and via
``start_rewrite`` for direct callers — so request validation, the
chapter-ownership gate (IDOR S6), and the conflict check stay ahead of
BOTH cascades (model routing + token limits) and an unconfigured
provider surfaces as a loud 400 before any SSE headers exist.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.writing._helpers import create_request_row, verify_chapter_access
from narrare.writing._rewrite_support import (
    RewriteRuntime,
    build_pipeline_request,
    build_rewrite_stream_inputs,
    mark_rewrite_failed,
)
from narrare.writing.schemas import GenerateResponse
from narrare_core.shared.errors import ConflictError, ValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.novels.repository import NovelRepository
    from narrare.settings.custom_tone_service import CustomToneService
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.schemas_rewrite import RewriteRequest
    from narrare_core.llm.result import StreamChunk
    from narrare_core.writing.draft_processor import DraftProcessor

logger = structlog.get_logger(__name__)


class RewriteService:
    """Orchestrates selection rewriting via pipeline + repository (DI, RULE-07).

    Uses the SSE-direct pattern: ``stream_rewrite()`` creates the request
    row AND streams the result.  The frontend receives SSE events directly.
    Accept/reject endpoints from the main writing router still work because
    they key off the ``generation_request.id`` included in the final SSE event.

    Args:
        repo: Generation request repository (status lifecycle + rows).
        runtime_factory: Zero-arg async callable returning the
            :class:`RewriteRuntime` — the DI factory's deferred
            composition over the REWRITE routing cascade and the
            token-limits cascade (ADR-086: invoked once at first use,
            never at construction).
        draft_processor: Draft post-processor (shared with the pipeline).
        chapter_repo: Chapter repository for the access gate (IDOR S6).
        novel_repo: Novel repository for the access gate (IDOR S6).
        tone_service: Optional custom-tone resolver.
        relationship_repo: Optional KB relationship source (FIND-009).
    """

    def __init__(
        self,
        repo: GenerationRepository,
        runtime_factory: Callable[[], Awaitable[RewriteRuntime]],
        draft_processor: DraftProcessor,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        tone_service: CustomToneService | None = None,
        relationship_repo: RelationshipRepository | None = None,
    ) -> None:
        self._repo = repo
        self._runtime_factory = runtime_factory
        self._runtime: RewriteRuntime | None = None
        self._draft_processor = draft_processor
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._tone_service = tone_service
        self._relationship_repo = relationship_repo

    # -- Lazy runtime (ADR-086) --------------------------------------------

    async def ensure_resolved(self) -> RewriteRuntime:
        """Compose the effective rewrite runtime at first use; idempotent.

        Invokes the factory's deferred composition — the REWRITE routing
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
        check, and any request-row creation.  The lazy runtime
        composition (ADR-086) runs LAST — after all gates — so gate
        failures keep precedence over an unconfigured provider's 400,
        and that 400 itself still fires before any SSE headers are sent.

        Raises:
            NotFoundError: Chapter unknown, not in the addressed novel,
                or novel owned by another user.
            ValidationError: If selection_text is empty.
            ConflictError: If another generation is active for the chapter.
            narrare_core.shared.errors.ConfigurationError: If the user
                has no AI provider configured (first-use composition).
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

        # ADR-086 L33: first-use lazy composition of BOTH cascades
        # (routing + token limits, incl. the tier-wired pipeline) —
        # post-validation and post-gate — so an unconfigured provider
        # stays a loud pre-header 400 (RULE-11), never a preempting
        # factory-time error.
        await self.ensure_resolved()

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
        # Step 1: Create the request row (validates input + checks concurrency).
        response = await self.start_rewrite(chapter_id, novel_id, user_id, request)
        request_id = response.request_id

        # ADR-086 L33: first-use lazy runtime (idempotent — the router's
        # pre-stream validate_rewrite already composed it on this
        # request; direct callers compose here, after validation).
        runtime = await self.ensure_resolved()

        # Step 2: Transition to streaming.
        await self._repo.update_status(
            request_id,
            "streaming",
            started_at=datetime.now(UTC),
            model_id=runtime.config.model_id,
            provider_name=runtime.config.provider_name,
        )

        # Step 3: Build pipeline request with rewrite-specific parameters.
        pipeline_request = build_pipeline_request(
            request_id, chapter_id, novel_id, user_id, request
        )

        # Step 4: Build chapter_content for rewrite: the selection text is
        # the primary content.  Context markers provide surrounding text.
        # Steps 5-6b (tone instructions, mode inputs, KB relationships)
        # assemble with it in the support module (RULE-04 split).
        inputs = await build_rewrite_stream_inputs(
            request=request,
            user_id=UUID(user_id),
            tone_service=self._tone_service,
            relationship_repo=self._relationship_repo,
            novel_id=novel_id,
        )

        # Step 7: Stream via pipeline (RULE-01b, RULE-02).
        accumulated: list[str] = []
        try:
            async for chunk in runtime.pipeline.generate(
                pipeline_request,
                config=runtime.config,
                api_key=runtime.api_key,
                base_url=runtime.base_url,
                chapter_content=inputs.chapter_content,
                custom_tone_instructions=inputs.custom_tone_instructions,
                selection_text=request.selection_text,
                context_before=request.context_before or "",
                context_after=request.context_after or "",
                rewrite_mode=inputs.rewrite_mode,
                custom_instructions=inputs.custom_instructions,
                rewrite_count=request.count,
                kb_relationships=inputs.kb_relationships,
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
            await mark_rewrite_failed(self._repo, self._draft_processor, request_id, accumulated, e)
