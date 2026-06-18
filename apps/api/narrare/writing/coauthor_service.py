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
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError

from narrare.writing._helpers import record_feedback
from narrare_core.shared.errors import ConflictError, NotFoundError, ValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.schemas_coauthor import CoAuthorRequest
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.result import StreamChunk
    from narrare_core.memory.protocols import FeedbackCollector
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)


class CoAuthorService:
    """Orchestrates co-author revision via pipeline + repository (SSE-direct).

    Uses the SSE-direct pattern: ``stream_coauthor()`` creates the request
    row AND streams the result.  The frontend receives SSE events directly,
    including change metadata in the final event.

    Dependencies are injected via constructor (DI pattern, RULE-07).
    """

    def __init__(
        self,
        repo: GenerationRepository,
        pipeline: WritingPipeline,
        draft_processor: DraftProcessor,
        config: ResolvedModelConfig,
        feedback_service: FeedbackCollector | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        relationship_repo: RelationshipRepository | None = None,
        max_selection_words: int = 2000,
    ) -> None:
        self._repo = repo
        self._pipeline = pipeline
        self._draft_processor = draft_processor
        self._config = config
        self._feedback = feedback_service
        self._api_key = api_key
        self._base_url = base_url
        self._relationship_repo = relationship_repo
        self._max_selection_words = max_selection_words

    # -- Public API ------------------------------------------------------------

    async def validate_coauthor(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        request: CoAuthorRequest,
    ) -> None:
        """Pre-validate co-author request before starting SSE response.

        Called by the router BEFORE creating the StreamingResponse to
        ensure validation errors (422, 409, 404) are returned with proper
        HTTP status codes instead of causing RuntimeError after headers
        are sent.

        Raises:
            ValidationError: If selection_text is empty or focus is empty.
            ConflictError: If another generation is active for the chapter.
            NotFoundError: If the chapter or novel does not exist.
        """
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

        if not await self._repo.chapter_exists(chapter_id):
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        active = await self._repo.get_active_for_chapter(chapter_id)
        if active is not None:
            raise ConflictError(f"Generation already active for chapter {chapter_id}")

        # SET-005 Cascade: user → project → env → code default (2000 words)
        word_count = len(request.selection_text.split())
        max_words = self._max_selection_words
        if word_count > max_words:
            raise ValidationError(
                f"Selection exceeds {max_words} words (got {word_count})",
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
        from narrare_core.writing._enums import GenerationMode
        from narrare_core.writing.models import (
            GenerationRequest as CoreGenerationRequest,
        )

        # Step 1: Validate and create the request row.
        await self.validate_coauthor(chapter_id, novel_id, request)
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

        # Step 2: Transition to streaming.
        await self._repo.update_status(
            request_id,
            "streaming",
            started_at=datetime.now(UTC),
            model_id=self._config.model_id,
            provider_name=self._config.provider_name,
        )

        # Step 3: Build pipeline request with co-author-specific parameters.
        pipeline_request = CoreGenerationRequest(
            id=request_id,
            chapter_id=chapter_id,
            project_id=novel_id,
            user_id=UUID(user_id),
            mode=GenerationMode.CO_AUTHOR,
            tone=request.tone,
            word_target=0,  # Co-author doesn't use word targets
            writing_language=request.language,
        )

        # Step 4: Build chapter_content for co-author: the selection text
        # is the primary content.  Context markers provide surrounding text.
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

        # Step 5: Convert focus areas to string list for the pipeline.
        focus_list = [f.value for f in request.focus]

        # Step 5b: Fetch and format KB relationships for prompt context (FIND-009)
        from narrare.writing._relationship_helpers import fetch_formatted_relationships

        kb_relationships = await fetch_formatted_relationships(
            self._relationship_repo,
            novel_id,
        )

        # Step 6: Stream via pipeline (RULE-01b, RULE-02).
        # The pipeline_coauthor module handles diff computation internally
        # and sends change metadata in the final chunk's context_meta.
        accumulated: list[str] = []
        try:
            async for chunk in self._pipeline.generate(
                pipeline_request,
                config=self._config,
                api_key=self._api_key,
                base_url=self._base_url,
                chapter_content=chapter_content,
                selection_text=request.selection_text,
                context_before=request.context_before or "",
                context_after=request.context_after or "",
                co_author_focus=focus_list,
                kb_relationships=kb_relationships.text,
            ):
                if chunk.is_final:
                    # Inject request_id into context_meta for feedback
                    # correlation (LEARN-001).
                    if chunk.context_meta:
                        chunk.context_meta["request_id"] = str(request_id)
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

                    # Record feedback (LEARN-001 integration)
                    request_model = await self._repo.get_by_id(request_id)
                    if request_model is not None:
                        await record_feedback(
                            self._feedback,
                            request_model,
                            "accept",
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
                "coauthor_stream_failed",
                request_id=str(request_id),
                chapter_id=str(chapter_id),
                error=str(e),
            )
