"""Style-variant regeneration service — SSE-direct variant streaming (CR-AUFG-07-22).

Creates a ``generation_request`` row and streams a style-variant regeneration
through the writing pipeline in one method call.  The frontend receives SSE
events directly from the dedicated endpoint.

The source operation mode is selected by ``StyleVariantRegenerateRequest.source_mode``:
``"rewrite"`` (Increment A) routes through the rewrite pipeline, ``"co_author"``
(Increment B) routes through the co-author pipeline.  In both cases the variant
direction is injected via the ``style_variant`` parameter, which flows through
``pipeline.generate()`` into the ``{{style_variant_instructions}}`` template variable.

Follows the same SSE-direct pattern as :class:`RewriteService` (separate class
per RULE-04/RULE-06).

Implements :class:`StyleVariantRegenerationProtocol` from
``contracts_style_variants.py`` (RULE-03).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError

from narrare_core.shared.errors import ConflictError, NotFoundError, ValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.writing.repository import GenerationRepository
    from narrare.writing.schemas_style_variants import StyleVariantRegenerateRequest
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.result import StreamChunk
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)


class StyleVariantService:
    """Orchestrates style-variant regeneration via pipeline + repository.

    Uses the SSE-direct pattern: ``stream_variant()`` creates the request
    row AND streams the variant result.  ``request.source_mode`` selects the
    source pipeline: ``"rewrite"`` uses ``rewrite_mode="style"`` with
    ``count=1`` (Increment A); ``"co_author"`` uses the CO_AUTHOR pipeline
    with ``co_author_focus=[]`` (Increment B).  In both modes the
    ``style_variant`` parameter carries the creative direction into the prompt.
    """

    def __init__(
        self,
        repo: GenerationRepository,
        pipeline: WritingPipeline,
        draft_processor: DraftProcessor,
        config: ResolvedModelConfig,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._repo = repo
        self._pipeline = pipeline
        self._draft_processor = draft_processor
        self._config = config
        self._api_key = api_key
        self._base_url = base_url

    # -- Public API --------------------------------------------------------

    async def validate_variant(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        request: StyleVariantRegenerateRequest,
    ) -> None:
        """Pre-validate the style-variant request before SSE response.

        Called by the router BEFORE creating the StreamingResponse to
        ensure validation errors (422, 409, 404) are returned with proper
        HTTP status codes instead of causing RuntimeError after headers
        are sent.

        Raises:
            ValidationError: If source_text is empty.
            ConflictError: If another generation is active for the chapter.
            NotFoundError: If the chapter or novel does not exist.
        """
        if not request.source_text.strip():
            raise ValidationError(
                "source_text must not be empty",
                code="MISSING_INPUT",
            )

        if not await self._repo.chapter_exists(chapter_id):
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        active = await self._repo.get_active_for_chapter(chapter_id)
        if active is not None:
            raise ConflictError(
                f"Generation already active for chapter {chapter_id}",
            )

    async def stream_variant(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: str,
        request: StyleVariantRegenerateRequest,
    ) -> AsyncIterator[StreamChunk]:
        """Create request row AND stream the style-variant generation.

        Internally validates input, creates a ``generation_request`` row,
        transitions to streaming, calls ``pipeline.generate()`` with the
        ``style_variant`` parameter, and handles status transitions
        (pending -> streaming -> completed/failed).

        The source operation mode is selected by ``request.source_mode``:

        * ``"rewrite"`` (default) — REWRITE pipeline with
          ``rewrite_mode="style"`` and ``count=1`` (Increment A behaviour).
        * ``"co_author"`` — CO_AUTHOR pipeline with ``co_author_focus=[]``
          so the variant direction is the only creative signal (Increment B).

        Args:
            chapter_id: Chapter the source output belongs to.
            novel_id: Novel the chapter belongs to.
            user_id: Authenticated user identifier.
            request: Variant request with source_text + style_variant.

        Yields:
            StreamChunk instances with incremental text.  The final
            chunk has ``is_final=True`` and populated ``usage``.
        """
        from narrare_core.writing._enums import GenerationMode
        from narrare_core.writing.models import (
            GenerationRequest as CoreGenerationRequest,
        )

        is_co_author = request.source_mode == "co_author"
        mode_enum = GenerationMode.CO_AUTHOR if is_co_author else GenerationMode.REWRITE

        # Step 1: Validate + create request row.
        await self.validate_variant(chapter_id, novel_id, request)

        try:
            request_id = await self._repo.create_if_no_active(
                chapter_id=chapter_id,
                novel_id=novel_id,
                user_id=UUID(user_id),
                mode=request.source_mode,
                tone=request.tone,
            )
        except IntegrityError as exc:
            raise NotFoundError("Chapter or Novel", identifier=str(chapter_id)) from exc

        # Step 2: Transition to streaming.
        await self._repo.update_status(
            request_id,
            "streaming",
            started_at=datetime.now(UTC),
            model_id=self._config.model_id,
            provider_name=self._config.provider_name,
        )

        logger.info(
            "style_variant_started",
            request_id=str(request_id),
            chapter_id=str(chapter_id),
            source_mode=request.source_mode,
            style_variant=request.style_variant.value,
        )

        # Step 3: Build pipeline request (mode selected by source_mode).
        pipeline_request = CoreGenerationRequest(
            id=request_id,
            chapter_id=chapter_id,
            project_id=novel_id,
            user_id=UUID(user_id),
            mode=mode_enum,
            tone=request.tone,
            word_target=0,
            writing_language=request.language,
        )

        # Step 4: Build chapter_content with context markers.
        chapter_content = request.source_text
        if request.context_before or request.context_after:
            parts: list[str] = []
            if request.context_before:
                parts.append(request.context_before)
            parts.append("[SELECTION START]")
            parts.append(request.source_text)
            parts.append("[SELECTION END]")
            if request.context_after:
                parts.append(request.context_after)
            chapter_content = "\n".join(parts)

        # Step 5: Stream via pipeline with style_variant (RULE-01b, RULE-02).
        # The invocation is branched by source_mode so that rewrite-specific
        # parameters (rewrite_mode/rewrite_count) are never passed in
        # CO_AUTHOR mode and vice versa.  Both calls share the streaming
        # loop below; only the mode-specific kwargs differ.  Keyword args
        # are spelled out (not unpacked from a dict) to stay mypy-strict
        # clean: ``generate`` has heterogeneous parameter types.
        if is_co_author:
            # co_author_focus=[] -> no area focus; the variant direction is
            # the sole creative signal (CR-AUFG-07-22 Increment B).
            stream: AsyncIterator[StreamChunk] = self._pipeline.generate(
                pipeline_request,
                config=self._config,
                api_key=self._api_key,
                base_url=self._base_url,
                chapter_content=chapter_content,
                selection_text=request.source_text,
                context_before=request.context_before or "",
                context_after=request.context_after or "",
                co_author_focus=[],
                style_variant=request.style_variant,
            )
        else:
            stream = self._pipeline.generate(
                pipeline_request,
                config=self._config,
                api_key=self._api_key,
                base_url=self._base_url,
                chapter_content=chapter_content,
                selection_text=request.source_text,
                context_before=request.context_before or "",
                context_after=request.context_after or "",
                rewrite_mode="style",
                rewrite_count=1,
                style_variant=request.style_variant,
            )

        accumulated: list[str] = []
        try:
            async for chunk in stream:
                # Context metadata event (CR-07): forward without accumulating.
                if chunk.context_meta is not None:
                    yield chunk
                    continue

                if chunk.is_final:
                    raw_text = "".join(accumulated) + chunk.text
                    cleaned = self._draft_processor.process(raw_text)
                    word_count = len(cleaned.split())
                    await self._repo.update_status(
                        request_id,
                        "completed",
                        tokens_used=(chunk.usage.total_tokens if chunk.usage else 0),
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
                "style_variant_stream_failed",
                request_id=str(request_id),
                error=str(e),
            )
            raise
