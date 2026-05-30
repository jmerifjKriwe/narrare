"""Co-Author service contract — written before implementation.

Follows the same SSE-direct pattern as :class:`RewriteServiceProtocol`.
Implements RULE-03: Contract before implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.writing.schemas_coauthor import CoAuthorRequest
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
