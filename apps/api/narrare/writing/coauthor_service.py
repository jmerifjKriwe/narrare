"""Co-author revision service — SSE-direct co-author generation.

Creates a ``generation_request`` row and streams co-author revisions
in one method call.  The frontend receives SSE events directly from
``POST /co-author`` — no separate ``GET /stream`` call needed.

Follows the same pattern as :class:`RewriteService` (separate service
class per RULE-04: WritingService is at its 300-line limit).

Implements :class:`CoAuthorServiceProtocol` from ``contracts_coauthor.py``
(RULE-03).  Diff computation happens server-side in the co-author pipeline
(:mod:`narrare_core.writing.pipeline_coauthor`) via the change engine
(:mod:`narrare_core.writing.change_engine`).  The service does NOT compute
diffs itself — it orchestrates the pipeline and passes through results.

Model acquisition is LAZY (ADR-086, M-budget): the factory wires a
``LazyModelResolution`` plus a deferred runtime composition; the service
resolves at first use — :meth:`ensure_resolved` at the end of
:meth:`validate_coauthor` (the router's pre-stream seam) and via
``stream_coauthor`` for direct callers — so request validation, the
chapter-ownership gate (IDOR S6), and the conflict check stay ahead of
BOTH cascades (model routing + token limits) and an unconfigured
provider surfaces as a loud 400 before any SSE headers exist.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError

from narrare.writing._coauthor_support import (
    CoAuthorRuntime,
    build_coauthor_stream_inputs,
    build_pipeline_request,
    mark_coauthor_completed,
    mark_coauthor_failed,
)
from narrare.writing._helpers import verify_chapter_access
from narrare_core.shared.errors import ConflictError, NotFoundError, ValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.novels.repository import NovelRepository
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.schemas_coauthor import CoAuthorRequest
    from narrare_core.llm.result import StreamChunk
    from narrare_core.memory.protocols import FeedbackCollector
    from narrare_core.writing.draft_processor import DraftProcessor

logger = structlog.get_logger(__name__)


class CoAuthorService:
    """Orchestrates co-author revision via pipeline + repository (SSE-direct).

    Uses the SSE-direct pattern: ``stream_coauthor()`` creates the request
    row AND streams the result.  The frontend receives SSE events directly,
    including change metadata in the final event.

    Args:
        repo: Generation request repository (status lifecycle + rows).
        runtime_factory: Zero-arg async callable returning the
            :class:`CoAuthorRuntime` — the DI factory's deferred
            composition over the CO_AUTHOR routing cascade and the
            token-limits cascade (ADR-086: invoked once at first use,
            never at construction).
        draft_processor: Draft post-processor (shared with the pipeline).
        chapter_repo: Chapter repository for the access gate (IDOR S6).
        novel_repo: Novel repository for the access gate (IDOR S6).
        feedback_service: Optional feedback collector (LEARN-001).
        relationship_repo: Optional KB relationship source (FIND-009).
    """

    def __init__(
        self,
        repo: GenerationRepository,
        runtime_factory: Callable[[], Awaitable[CoAuthorRuntime]],
        draft_processor: DraftProcessor,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        feedback_service: FeedbackCollector | None = None,
        relationship_repo: RelationshipRepository | None = None,
    ) -> None:
        self._repo = repo
        self._runtime_factory = runtime_factory
        self._runtime: CoAuthorRuntime | None = None
        self._draft_processor = draft_processor
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._feedback = feedback_service
        self._relationship_repo = relationship_repo

    # -- Lazy runtime (ADR-086) --------------------------------------------

    async def ensure_resolved(self) -> CoAuthorRuntime:
        """Compose the effective co-author runtime at first use; idempotent.

        Invokes the factory's deferred composition — the CO_AUTHOR
        routing cascade AND the token-limits cascade, the sampling
        overrides, the ADR-082 budgets, the tier-wired pipeline, and the
        SET-005 selection-word limit — exactly once; the frozen result
        is cached for the service's lifetime.  Errors propagate
        uncached (RULE-11): ``ConfigurationError`` (``NO_AI_PROVIDER``)
        surfaces as a pre-header 400 on this SSE endpoint.
        """
        if self._runtime is None:
            self._runtime = await self._runtime_factory()
        return self._runtime

    # -- Public API ------------------------------------------------------------

    async def validate_coauthor(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        request: CoAuthorRequest,
        *,
        user_id: str,
    ) -> None:
        """Pre-validate co-author request before starting SSE response.

        Ownership gate (IDOR S6): ``verify_chapter_access`` runs FIRST —
        foreign ≡ unknown 404s precede input validation, the conflict
        check, and any request-row creation.

        Raises:
            NotFoundError: Chapter unknown, not in the addressed novel,
                or novel owned by another user.
            ValidationError: If selection_text is empty, focus is empty,
                or the selection exceeds the SET-005 word limit.
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

        if not request.focus:
            raise ValidationError(
                "focus must contain at least one area",
                code="MISSING_INPUT",
            )

        active = await self._repo.get_active_for_chapter(chapter_id)
        if active is not None:
            raise ConflictError(f"Generation already active for chapter {chapter_id}")

        # ADR-086 L31: first-use lazy composition of BOTH cascades
        # (routing + token limits, incl. the tier-wired pipeline) —
        # post-validation and post-gate — so an unconfigured provider
        # stays a loud pre-header 400 (RULE-11), never a preempting
        # factory-time error.
        runtime = await self.ensure_resolved()

        # SET-005 Cascade: user → project → env → code default (2000
        # words).  The limit is a token-limits-cascade output, so under
        # the lazy wiring this check necessarily runs AT first use —
        # still pre-header and before any request-row creation.
        word_count = len(request.selection_text.split())
        if word_count > runtime.max_selection_words:
            raise ValidationError(
                f"Selection exceeds {runtime.max_selection_words} words (got {word_count})",
                code="SELECTION_TOO_LONG",
            )

    async def stream_coauthor(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: str,
        request: CoAuthorRequest,
    ) -> AsyncIterator[StreamChunk]:
        """Create request row AND stream co-author revision (SSE-direct).

        Internally creates a ``generation_request`` row with mode
        ``"co_author"``, then streams the revised text through the
        pipeline.  After streaming completes, the pipeline computes a
        server-side diff and includes change metadata in the final
        chunk's ``context_meta``.

        Args:
            chapter_id: Chapter containing the selection to revise.
            novel_id: Novel the chapter belongs to.
            user_id: Authenticated user identifier.
            request: Co-author-specific parameters (selection_text,
                context, focus, tone, language).

        Yields:
            StreamChunk instances with incremental text.  The final
            chunk has ``is_final=True``, ``usage``, and diff data in
            ``context_meta`` (changes, total_changes, has_changes).
        """
        # Step 1: Validate (ownership gate first) and create the request row.
        await self.validate_coauthor(chapter_id, novel_id, request, user_id=user_id)
        try:
            request_id = await self._repo.create(
                chapter_id=chapter_id,
                novel_id=novel_id,
                user_id=UUID(user_id),
                mode="co_author",
                tone=request.tone,
            )
        except IntegrityError as exc:
            raise NotFoundError("Chapter or Novel", identifier=str(chapter_id)) from exc

        logger.info(
            "coauthor_started",
            request_id=str(request_id),
            chapter_id=str(chapter_id),
            focus=[f.value for f in request.focus],
        )

        # ADR-086 L31: first-use lazy runtime (idempotent — the router's
        # pre-stream validate_coauthor already composed it on this
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

        # Step 3: Build pipeline request with co-author-specific
        # parameters, plus the selection-marker content block and the
        # formatted KB relationships (FIND-009) — support module
        # (RULE-04 split).
        pipeline_request = build_pipeline_request(
            request_id, chapter_id, novel_id, user_id, request
        )
        inputs = await build_coauthor_stream_inputs(
            request=request,
            relationship_repo=self._relationship_repo,
            novel_id=novel_id,
        )

        # Step 5: Convert focus areas to string list for the pipeline.
        focus_list = [f.value for f in request.focus]

        # Step 6: Stream via pipeline (RULE-01b, RULE-02).
        # The pipeline_coauthor module handles diff computation internally
        # and sends change metadata in the final chunk's context_meta.
        accumulated: list[str] = []
        try:
            async for chunk in runtime.pipeline.generate(
                pipeline_request,
                config=runtime.config,
                api_key=runtime.api_key,
                base_url=runtime.base_url,
                chapter_content=inputs.chapter_content,
                selection_text=request.selection_text,
                context_before=request.context_before or "",
                context_after=request.context_after or "",
                co_author_focus=focus_list,
                kb_relationships=inputs.kb_relationships,
            ):
                if chunk.is_final:
                    # Inject request_id into context_meta for feedback
                    # correlation (LEARN-001).
                    if chunk.context_meta:
                        chunk.context_meta["request_id"] = str(request_id)
                    await mark_coauthor_completed(
                        self._repo,
                        self._draft_processor,
                        request_id,
                        accumulated,
                        chunk.text,
                        chunk.usage,
                        self._feedback,
                    )

                    yield chunk
                    return
                accumulated.append(chunk.text)
                yield chunk
        except Exception as e:
            await mark_coauthor_failed(
                self._repo, self._draft_processor, request_id, accumulated, e, chapter_id
            )
