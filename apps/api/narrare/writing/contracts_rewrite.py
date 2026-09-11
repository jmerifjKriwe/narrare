"""Rewrite service contract — written before implementation.

Split from ``contracts.py`` per RULE-04 (the main contracts file exceeded
its 200-line hard limit after adding the extend protocol).

Implements RULE-03: Contract before implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.writing.schemas import GenerateResponse
    from narrare.writing.schemas_rewrite import RewriteRequest
    from narrare_core.llm.result import StreamChunk


@runtime_checkable
class RewriteServiceProtocol(Protocol):
    """Protocol for the rewrite selection service (SSE-direct pattern).

    Creates a ``generation_request`` row and streams rewrite alternatives
    in one method call.  The frontend receives SSE events directly from
    ``POST /rewrite`` — no separate ``GET /stream`` call needed.
    """

    async def validate_rewrite(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        request: RewriteRequest,
        *,
        user_id: str,
    ) -> None:
        """Pre-validate rewrite request before starting SSE response.

        Ownership gate (IDOR remediation S6): the chapter must exist,
        belong to the addressed novel, and the novel must belong to the
        caller — foreign and unknown ids are indistinguishable 404s
        raised BEFORE any input validation, active-generation check, or
        request-row creation.

        Raises:
            NotFoundError: If the chapter does not exist, does not
                belong to the addressed novel, or the novel belongs to
                another user.
            ValidationError: If selection_text is empty.
            ConflictError: If another generation is active.
        """
        ...

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
        ...

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
            StreamChunk instances with incremental text.  The final
            chunk has ``is_final=True`` and populated ``usage``.
        """
        ...
