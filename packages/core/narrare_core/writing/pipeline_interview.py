"""Interview-assisted generation mode.

Split from pipeline.py to respect RULE-04 (file size limit).
Generates interview questions via LLM; the API layer collects answers
and calls the pipeline again in ``full_draft`` mode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.result import StreamChunk
from narrare_core.prompts.context import PromptContext
from narrare_core.shared.errors import WritingError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.writing.models import GenerationRequest, WritingContext
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)


async def stream_interview_assisted(
    pipeline: WritingPipeline,
    request: GenerationRequest,
    context: WritingContext,
    config: ResolvedModelConfig,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> AsyncIterator[StreamChunk]:
    """Generate interview questions for the writer.

    The API layer handles the interactive interview loop and then
    calls the pipeline again with ``full_draft`` mode, using the
    collected answers as ``request.prompt``.
    """
    prompt_context = PromptContext(
        language=context.language,
        project_title=context.project_title,
        genre=context.genre,
        mode="interview",
        author_instructions=request.outline or request.prompt or "",
        extra={
            "user_id": str(request.user_id),
            "project_id": str(request.project_id),
            "chapter_outline": context.chapter_outline,
            "kb_characters": context.kb_characters,
            "recent_chapters": context.recent_chapters,
        },
    )
    prompt = await pipeline._composer.build(LLMIntent.CHAT, prompt_context)  # pyright: ignore[reportPrivateUsage]

    try:
        result_text: str = await pipeline._registry.run(  # pyright: ignore[reportPrivateUsage,reportUnknownVariableType]
            LLMIntent.CHAT,
            prompt=prompt.user,
            config=config,
            system_prompt=prompt.system,
            api_key=api_key,
            base_url=base_url,
        )
    except Exception as e:
        raise WritingError(
            f"Interview question generation failed: {e}",
            code="INTERVIEW_FAILED",
        ) from e

    # ModelRegistry.run() returns str, not LLMResult — wrap for compatibility
    yield StreamChunk(text=result_text)
    yield StreamChunk(text="", is_final=True, usage=None)
