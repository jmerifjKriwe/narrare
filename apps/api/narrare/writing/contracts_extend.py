"""Extend service contract — written before implementation.

Split from ``contracts.py`` per RULE-04 (the main contracts file exceeded
200-line hard limit after adding the extend protocol).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.writing.schemas import ExtendRequest, GenerateResponse
    from narrare_core.llm.result import StreamChunk


@runtime_checkable
class ExtendServiceProtocol(Protocol):
    """Protocol for the extend chapter service (SSE-direct pattern).

    Creates a generation_request row and streams the extension in one
    method call.  The frontend receives SSE events directly from
    ``POST /extend`` — no separate ``GET /stream`` call needed.
    """

    async def validate_extend(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        request: ExtendRequest,
    ) -> None:
        """Pre-validate extend request before starting SSE response.

        Raises:
            ValidationError: If text_before is empty.
            ConflictError: If another generation is active.
            NotFoundError: If chapter does not exist.
        """
        ...

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
        ...

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
            StreamChunk instances with incremental text.  The final
            chunk has ``is_final=True`` and populated ``usage``.
        """
        ...
