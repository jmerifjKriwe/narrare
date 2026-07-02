"""Mode dispatch — routes a generation request to its mode-specific streamer.

Extracts the ``request.mode`` if/elif dispatch out of
:meth:`WritingPipeline.generate` (RULE-04: modularize, not minify; RULE-06:
one responsibility per module). Each :class:`GenerationMode` maps to exactly
one sibling streaming module:

    FULL_DRAFT          → :func:`pipeline_graph.stream_via_writing_graph`
    EXTEND              → :func:`pipeline_extend.stream_extend`
    REWRITE             → :func:`pipeline_rewrite.stream_rewrite`
    SCENE_BY_SCENE      → :func:`pipeline_scene.stream_scene_by_scene`
    INTERVIEW_ASSISTED  → :func:`pipeline_interview.stream_interview_assisted`
    CO_AUTHOR           → :func:`pipeline_coauthor.stream_coauthor`
    INTERACTIVE_SESSION → raises ``ValueError`` (WebSocket-only)

This is a pure structural extraction — no behavioural change. Prompt and
agent abstractions are NOT bypassed: every per-mode streamer still goes
through the injected :class:`PromptComposer` / agent / registry paths.

Contract (AUFG-01-08 stage 4 — dispatch + invocation):

    ``stream_for_mode(pipeline, request, context, config, *, <mode params>)``
        in:  the owning WritingPipeline (its helpers/deps are forwarded to
             the per-mode streamers, which already receive ``self`` today),
             the assembled WritingContext, the resolved model config, and the
             mode-specific call parameters.
        out: ``AsyncIterator[StreamChunk]`` — the raw mode output. Budget
             resolution, prompt build and the LLM call all happen *inside*
             each mode module, never here.

``pipeline`` is passed because the existing per-mode streamers take the
pipeline instance as their first argument (e.g. ``stream_extend(self, …)``)
to reach ``_build_prompt_context`` / ``_build_and_validate_prompt`` /
``_is_stopped``. This preserves the established intra-package coupling
without introducing new dependencies.

This module is internal to the writing subsystem — not part of the public API.

See:
    AUFG-01-08, CONSTRAINTS.md RULE-04 / RULE-06.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.shared.errors import WritingError
from narrare_core.writing._enums import GenerationMode

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.result import StreamChunk
    from narrare_core.writing.models import GenerationRequest, WritingContext
    from narrare_core.writing.pipeline import WritingPipeline
    from narrare_core.writing.style_variants import StyleVariant


async def stream_for_mode(
    pipeline: WritingPipeline,
    request: GenerationRequest,
    context: WritingContext,
    config: ResolvedModelConfig,
    *,
    api_key: str | None,
    base_url: str | None,
    selection_text: str,
    context_before: str,
    context_after: str,
    rewrite_mode: str,
    custom_instructions: str,
    rewrite_count: int,
    custom_tone_instructions: str | None,
    co_author_focus: list[str] | None,
    style_variant: StyleVariant | None,
) -> AsyncIterator[StreamChunk]:
    """Dispatch ``request`` to its mode-specific streaming function.

    Args:
        pipeline: Owning WritingPipeline (helpers/deps forwarded to streamers).
        request: The generation request (``request.mode`` selects the branch).
        context: Assembled WritingContext from Stage 2.
        config: Resolved model configuration for the LLM call.
        api_key: Optional API key override.
        base_url: Optional base URL override.
        selection_text: Text selection (REWRITE / CO_AUTHOR).
        context_before: Text immediately before the selection.
        context_after: Text immediately after the selection.
        rewrite_mode: Rewrite strategy (tone/style/voice/fix/custom).
        custom_instructions: Author rewrite instructions (custom mode).
        rewrite_count: Number of rewrite alternatives (1-3).
        custom_tone_instructions: User-defined tone (EXTEND override).
        co_author_focus: Focus areas for CO_AUTHOR mode (``None`` = none).
        style_variant: Optional creative-direction variant
            (REWRITE / CO_AUTHOR); ``None`` renders the variable empty.

    Yields:
        StreamChunk: Output chunks from the selected mode streamer.

    Raises:
        ValueError: For ``INTERACTIVE_SESSION`` (WebSocket-only).
        WritingError: For an unsupported / unknown mode.
    """
    if request.mode == GenerationMode.FULL_DRAFT:
        from narrare_core.writing.pipeline_graph import stream_via_writing_graph

        # FULL_DRAFT's streamer takes the collaborators explicitly (unlike the
        # other modes, which receive ``pipeline`` as their first argument).
        # Reached from this sibling module, hence the coded reportPrivateUsage
        # suppressions — same pattern as pipeline_extend.py::_tone_instructions.
        async for chunk in stream_via_writing_graph(
            request,
            context,
            config,
            registry=pipeline._registry,  # pyright: ignore[reportPrivateUsage]
            composer=pipeline._composer,  # pyright: ignore[reportPrivateUsage]
            context_assembler=pipeline._context_assembler,  # pyright: ignore[reportPrivateUsage]
            api_key=api_key,
            base_url=base_url,
            agent_registry=pipeline._agent_registry,  # pyright: ignore[reportPrivateUsage]
            invocation_pipeline=pipeline._invocation_pipeline,  # pyright: ignore[reportPrivateUsage]
        ):
            yield chunk

    elif request.mode == GenerationMode.EXTEND:
        from narrare_core.writing.pipeline_extend import stream_extend

        async for chunk in stream_extend(
            pipeline,
            request,
            context,
            config,
            api_key=api_key,
            base_url=base_url,
            custom_tone_instructions=custom_tone_instructions,
        ):
            yield chunk

    elif request.mode == GenerationMode.REWRITE:
        from narrare_core.writing.pipeline_rewrite import stream_rewrite

        async for chunk in stream_rewrite(
            pipeline,
            request,
            context,
            config,
            api_key=api_key,
            base_url=base_url,
            selection_text=selection_text,
            context_before=context_before,
            context_after=context_after,
            rewrite_mode=rewrite_mode,
            custom_instructions=custom_instructions,
            count=rewrite_count,
            style_variant=style_variant,
        ):
            yield chunk

    elif request.mode == GenerationMode.SCENE_BY_SCENE:
        from narrare_core.writing.pipeline_scene import stream_scene_by_scene

        async for chunk in stream_scene_by_scene(
            pipeline,
            request,
            context,
            config,
            api_key=api_key,
            base_url=base_url,
        ):
            yield chunk

    elif request.mode == GenerationMode.INTERVIEW_ASSISTED:
        from narrare_core.writing.pipeline_interview import stream_interview_assisted

        async for chunk in stream_interview_assisted(
            pipeline,
            request,
            context,
            config,
            api_key=api_key,
            base_url=base_url,
        ):
            yield chunk

    elif request.mode == GenerationMode.INTERACTIVE_SESSION:
        raise ValueError("Interactive session uses WebSocket, not pipeline.generate()")

    elif request.mode == GenerationMode.CO_AUTHOR:
        from narrare_core.writing.pipeline_coauthor import stream_coauthor

        async for chunk in stream_coauthor(
            pipeline,
            request,
            context,
            config,
            api_key=api_key,
            base_url=base_url,
            selection_text=selection_text,
            context_before=context_before,
            context_after=context_after,
            focus=co_author_focus,
            style_variant=style_variant,
        ):
            yield chunk

    else:
        raise WritingError(
            f"Unsupported generation mode: {request.mode}",
            code="UNSUPPORTED_MODE",
        )
