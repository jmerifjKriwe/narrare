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

from narrare.writing._helpers import create_request_row, verify_chapter_access
from narrare.writing._style_variants_support import build_variant_content, mark_variant_failed
from narrare_core.shared.errors import ConflictError, ValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.writing._style_variants_support import StyleVariantRuntime
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.schemas_style_variants import StyleVariantRegenerateRequest
    from narrare_core.llm.result import StreamChunk
    from narrare_core.writing.draft_processor import DraftProcessor

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
        runtime_factory: Callable[[], Awaitable[StyleVariantRuntime]],
        draft_processor: DraftProcessor,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
    ) -> None:
        self._repo = repo
        self._runtime_factory = runtime_factory
        self._runtime: StyleVariantRuntime | None = None
        self._draft_processor = draft_processor
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo

    # -- Lazy runtime (ADR-086) --------------------------------------------

    async def ensure_resolved(self) -> StyleVariantRuntime:
        """Compose the effective style-variant runtime at first use; idempotent.

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

    async def validate_variant(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        request: StyleVariantRegenerateRequest,
        *,
        user_id: str,
    ) -> None:
        """Pre-validate the style-variant request before SSE response.

        Ownership gate (IDOR S6): ``verify_chapter_access`` runs FIRST —
        foreign ≡ unknown 404s precede input validation, the conflict
        check, and any request-row creation.  The lazy runtime
        composition (ADR-086) runs LAST — after all gates — so gate
        failures keep precedence over an unconfigured provider's 400,
        and that 400 itself still fires before any SSE headers are sent.

        Raises:
            NotFoundError: Chapter unknown, not in the addressed novel,
                or novel owned by another user.
            ValidationError: If source_text is empty.
            ConflictError: If another generation is active for the chapter.
            narrare_core.shared.errors.ConfigurationError: If the user
                has no AI provider configured (first-use composition).
        """
        await verify_chapter_access(
            self._chapter_repo, self._novel_repo, chapter_id, novel_id, user_id
        )

        if not request.source_text.strip():
            raise ValidationError(
                "source_text must not be empty",
                code="MISSING_INPUT",
            )

        active = await self._repo.get_active_for_chapter(chapter_id)
        if active is not None:
            raise ConflictError(
                f"Generation already active for chapter {chapter_id}",
            )

        # ADR-086 L35: first-use lazy composition of BOTH cascades
        # (routing + token limits, incl. the tier-wired pipeline) —
        # post-validation and post-gate — so an unconfigured provider
        # stays a loud pre-header 400 (RULE-11), never a preempting
        # factory-time error.
        await self.ensure_resolved()

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

        # Step 1: Validate (ownership gate first) + create request row.
        # validate_variant is the pre-stream seam: its trailing first-use
        # composition (ADR-086) has the runtime ready when we get here.
        await self.validate_variant(chapter_id, novel_id, request, user_id=user_id)
        request_id = await create_request_row(
            self._repo, chapter_id, novel_id, user_id, request.source_mode, request.tone
        )

        # Step 2: Transition to streaming.  The runtime is already
        # composed (ADR-086): the pre-stream validate_variant above ran
        # the first-use composition on this service instance, so
        # ensure_resolved here is a cached read.
        runtime = await self.ensure_resolved()
        await self._repo.update_status(
            request_id,
            "streaming",
            started_at=datetime.now(UTC),
            model_id=runtime.config.model_id,
            provider_name=runtime.config.provider_name,
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

        # Step 4: Build chapter_content with context markers
        # (_style_variants_support, RULE-04 extraction).
        chapter_content = build_variant_content(request)

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
            stream: AsyncIterator[StreamChunk] = runtime.pipeline.generate(
                pipeline_request,
                config=runtime.config,
                api_key=runtime.api_key,
                base_url=runtime.base_url,
                chapter_content=chapter_content,
                selection_text=request.source_text,
                context_before=request.context_before or "",
                context_after=request.context_after or "",
                co_author_focus=[],
                style_variant=request.style_variant,
            )
        else:
            stream = runtime.pipeline.generate(
                pipeline_request,
                config=runtime.config,
                api_key=runtime.api_key,
                base_url=runtime.base_url,
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
            await mark_variant_failed(
                self._repo,
                self._draft_processor,
                request_id,
                accumulated,
                e,
            )
            raise
