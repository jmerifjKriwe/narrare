"""Style-variant regeneration service contract — written before implementation.

Split into its own file per RULE-04 (file-size limit) and RULE-06 (one
responsibility per file).  Implements RULE-03: Contract before implementation.

CR-AUFG-07-22 Increment A: Rewrite + generated-draft variant regeneration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.writing.schemas_style_variants import StyleVariantRegenerateRequest
    from narrare_core.llm.result import StreamChunk


@runtime_checkable
class StyleVariantRegenerationProtocol(Protocol):
    """Protocol for regenerating an AI output in a controlled style variant.

    Creates a ``generation_request`` row and streams the variant via the
    rewrite pipeline with an injected ``style_variant`` parameter.  The
    frontend receives SSE events directly from the dedicated endpoint —
    no separate ``GET /stream`` call needed.

    Model/provider/token settings resolve through the existing cascade;
    the variant never changes providers.
    """

    async def validate_variant(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        request: StyleVariantRegenerateRequest,
        *,
        user_id: str,
    ) -> None:
        """Pre-validate the style-variant request before SSE response.

        Ownership gate (IDOR remediation S6): ``verify_chapter_access``
        runs FIRST — foreign and unknown chapter ids are indistinguishable
        404s raised before any input validation, active-generation check,
        or request-row creation.

        Raises:
            NotFoundError: Chapter unknown, not in the addressed novel,
                or novel owned by another user.
            ValidationError: If source_text is empty.
            ConflictError: If another generation is active for the chapter.
        """
        ...

    async def stream_variant(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: str,
        request: StyleVariantRegenerateRequest,
    ) -> AsyncIterator[StreamChunk]:
        """Create request row AND stream the style-variant generation (SSE-direct).

        Internally creates a ``generation_request`` row, transitions to
        streaming, calls ``pipeline.generate()`` with the ``style_variant``
        parameter, and yields ``StreamChunk`` instances.

        The request row ``mode`` follows ``request.source_mode``: ``"rewrite"``
        routes through the REWRITE pipeline (Increment A); ``"co_author"``
        routes through the CO_AUTHOR pipeline (Increment B).

        Args:
            chapter_id: Chapter the source output belongs to.
            novel_id: Novel the chapter belongs to.
            user_id: Authenticated user identifier.
            request: Variant request with source_text + style_variant.

        Yields:
            StreamChunk instances with incremental text.  The final
            chunk has ``is_final=True`` and populated ``usage``.
        """
        ...
