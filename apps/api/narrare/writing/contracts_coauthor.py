"""Co-Author service contract — written before implementation.

Follows the same SSE-direct pattern as :class:`RewriteServiceProtocol`.
Implements RULE-03: Contract before implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.chapters.models import Chapter
    from narrare.writing.schemas_coauthor import (
        ApplyChangesRequest,
        ChangeFeedback,
        CoAuthorRequest,
    )
    from narrare_core.llm.result import StreamChunk


@runtime_checkable
class CoAuthorServiceProtocol(Protocol):
    """Protocol for the co-author revision service (SSE-direct pattern).

    Creates a ``generation_request`` row and streams co-author revisions
    in one method call.  The frontend receives SSE events directly via
    ``POST /co-author`` — no separate ``GET /stream`` call needed.

    After streaming completes, the pipeline computes a server-side diff
    and includes change metadata in the final chunk's ``context_meta``.
    """

    async def validate_coauthor(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        request: CoAuthorRequest,
    ) -> None:
        """Pre-validate co-author request before starting SSE response.

        Checks:
        1. ``selection_text`` is not empty.
        2. ``focus`` list is not empty.
        3. Chapter exists in the database.
        4. No other generation is active for this chapter (conflict prevention).

        Raises:
            ValidationError: If selection_text is empty or focus is empty.
            ConflictError: If another generation is active for the chapter.
            NotFoundError: If the chapter or novel does not exist.
        """
        ...

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
        server-side diff via :mod:`narrare_core.writing.change_engine`
        and sends change metadata in the final chunk's ``context_meta``.

        Args:
            chapter_id: Chapter containing the selection to revise.
            novel_id: Novel the chapter belongs to.
            user_id: Authenticated user identifier.
            request: Co-author-specific parameters (selection_text,
                context, focus, etc.).

        Yields:
            StreamChunk instances with incremental text.  The final
            chunk has ``is_final=True``, ``usage``, and diff data in
            ``context_meta`` (changes, total_changes, has_changes).
        """
        ...

    async def apply_changes(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: str,
        request: ApplyChangesRequest,
    ) -> Chapter:
        """Apply accepted co-author changes to chapter content.

        Uses :func:`~narrare_core.writing.text_reconstructor.reconstruct_text`
        to rebuild the chapter text from original + accepted changes.
        Persists via ChapterRepository and records feedback for rejected
        changes via the FeedbackCollector.

        Args:
            chapter_id: Chapter to apply changes to.
            novel_id: Novel the chapter belongs to.
            user_id: Authenticated user identifier.
            request: Contains original selection text, accepted changes,
                rejected changes, and the generation request ID.

        Returns:
            Updated ``Chapter`` ORM model with reconstructed content.

        Raises:
            NotFoundError: If the generation request does not exist or
                belongs to another user, if the request row does not
                reference the addressed chapter and novel, or if the
                chapter does not exist.
        """
        ...

    async def record_feedback(
        self,
        request_id: UUID,
        feedback: list[ChangeFeedback],
        user_id: str,
    ) -> None:
        """Record batch per-change feedback for co-author (LEARN-001).

        Creates individual ``FeedbackEvent`` entries for each change
        feedback item.  Silently no-ops when no ``FeedbackCollector``
        is configured.  Events are always stamped with the request
        row's user — the ownership gate guarantees that row belongs to
        the caller, so feedback can never pollute another user's
        preference learning.

        Args:
            request_id: The generation request ID these changes belong to.
            feedback: Per-change feedback items with action and metadata.
            user_id: Authenticated user identifier (access check).

        Raises:
            NotFoundError: If the generation request does not exist or
                belongs to another user.
        """
        ...
