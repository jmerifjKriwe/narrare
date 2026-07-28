"""Extend generation mode — seamless continuation from cursor position.

Split from pipeline.py to respect RULE-04 (file size limit).
Direct LLM call (no WritingGraph) — quality comes from prompt
construction (style analysis + pre-text verbatim), not multi-step
agent reasoning.  See design.md D6.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.result import StreamChunk
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.writing.models import GenerationRequest, WritingContext
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)


async def stream_extend(
    pipeline: WritingPipeline,
    request: GenerationRequest,
    context: WritingContext,
    config: ResolvedModelConfig,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    custom_tone_instructions: str | None = None,
    default_word_target: int = 400,
) -> AsyncIterator[StreamChunk]:
    """Generate a seamless continuation from the cursor position.

    Constructs the PromptContext directly (not via ``_build_prompt_context``)
    because ``existing_content`` must contain the pre-text with the
    ``[CONTINUE FROM HERE]`` marker plus optional post-text — this is
    critical for the extend prompt.
    """
    # Word target: from request (set by API layer) or default
    word_target = request.word_target or default_word_target

    tone_instr = (
        custom_tone_instructions
        if custom_tone_instructions is not None
        else pipeline._tone_instructions(context.tone)  # pyright: ignore[reportPrivateUsage]
    )

    # Extra variables for prompt template rendering
    extra: dict[str, str] = {
        "user_id": str(request.user_id),
        "project_id": str(request.project_id),
        "chapter_outline": context.chapter_outline,
        "kb_characters": context.kb_characters,
        "kb_locations": context.kb_locations,
        "recent_chapters": context.recent_chapters,
        "character_voice_profiles": context.character_voice_profiles,
        "word_target": str(word_target),
        "tone_instructions": tone_instr,
        "writing_language": context.writing_language,
        "extend_length": str(word_target),
    }

    # Construct PromptContext directly — existing_content is critical.
    # The context assembler populates chapter_content with:
    #   pre-text + [CONTINUE FROM HERE] + post-text
    prompt_ctx = PromptContext(
        language=context.language,
        writing_language=context.writing_language,
        project_title=context.project_title,
        genre=context.genre,
        tone=context.tone,
        mode="extend_chapter",
        existing_content=context.chapter_content,
        author_instructions=request.prompt or request.outline or "",
        user_preferences=context.user_preferences,
        avoidance_patterns=context.avoidance_patterns,
        character_voice_profiles=context.character_voice_profiles,
        author_voice=context.author_voice,
        extra=extra,
    )

    # Compose prompt via RULE-02
    prompt = await pipeline._build_and_validate_prompt(  # pyright: ignore[reportPrivateUsage]
        LLMIntent.EXTEND,
        prompt_ctx,
        user_id=request.user_id,
        project_id=request.project_id,
    )

    # Stream from LLM via RULE-01b
    accumulated: list[str] = []
    async for chunk in pipeline._registry.stream(  # pyright: ignore[reportPrivateUsage]
        intent=LLMIntent.EXTEND,
        system_prompt=prompt.system,
        user_prompt=prompt.user,
        config=config,
        api_key=api_key,
        base_url=base_url,
    ):
        if pipeline._is_stopped(request.id):  # pyright: ignore[reportPrivateUsage]
            break

        if chunk.is_final:
            # Apply DraftProcessor on accumulated text
            raw_text = "".join(accumulated)
            final_text = pipeline._draft_processor.process(  # pyright: ignore[reportPrivateUsage]
                raw_text,
                word_target=word_target,
            )
            yield StreamChunk(text=final_text, is_final=True, usage=chunk.usage)
        else:
            accumulated.append(chunk.text)
            yield chunk
