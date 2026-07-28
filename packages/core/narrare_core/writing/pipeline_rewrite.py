"""Rewrite generation mode — selection rewriting with structured alternatives.

Split from pipeline.py to respect RULE-04 (file size limit).
Direct LLM call (no WritingGraph) — quality comes from prompt
construction (selection context + mode-specific strategy), not
multi-step agent reasoning.  See design.md D1, D3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.result import StreamChunk
from narrare_core.prompts.context import PromptContext
from narrare_core.writing.style_variants import StyleVariant, get_style_variant_instructions

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.writing.models import GenerationRequest, WritingContext
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Rewrite mode → strategy instructions
# ---------------------------------------------------------------------------

_REWRITE_MODE_INSTRUCTIONS: dict[str, str] = {
    "tone": (
        "Adjust the emotional language, pacing, and word choice to match the "
        "requested tone shift. Modify connotations, sensory details, and "
        "emotional register while preserving the underlying meaning and "
        "narrative structure."
    ),
    "style": (
        "Modify sentence structure, descriptive density, and active/passive "
        "voice balance. Adjust paragraph rhythm, vary sentence lengths, and "
        "shift the descriptive register while keeping the content intact."
    ),
    "voice": (
        "Rewrite using the character's established speech patterns, vocabulary, "
        "dialect, and verbal tics. The rewritten text should sound as if the "
        "character themselves wrote or narrated it, preserving their linguistic "
        "identity."
    ),
    "fix": (
        "Apply show-don't-tell techniques, remove redundancies, strengthen "
        "weak verbs, and fix awkward phrasing. Improve clarity and impact "
        "without changing the meaning or adding new content."
    ),
    "custom": (
        "Follow the custom instructions provided by the author precisely. "
        "Apply only the requested changes while maintaining the overall "
        "narrative voice and established facts."
    ),
}


def get_rewrite_mode_instructions(
    rewrite_mode: str,
    *,
    custom_instructions: str = "",
) -> str:
    """Return mode-specific rewrite strategy instructions.

    Args:
        rewrite_mode: One of "tone", "style", "voice", "fix", "custom".
        custom_instructions: Author-provided instructions (used when
            ``rewrite_mode`` is ``"custom"``).

    Returns:
        Strategy instructions string for the prompt template.
    """
    base = _REWRITE_MODE_INSTRUCTIONS.get(rewrite_mode, "")
    if rewrite_mode == "custom" and custom_instructions:
        return f"{base}\n\nAuthor's custom instructions: {custom_instructions}"
    return base


# ---------------------------------------------------------------------------
# Streaming rewrite
# ---------------------------------------------------------------------------


async def stream_rewrite(
    pipeline: WritingPipeline,
    request: GenerationRequest,
    context: WritingContext,
    config: ResolvedModelConfig,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    selection_text: str = "",
    context_before: str = "",
    context_after: str = "",
    rewrite_mode: str = "tone",
    custom_instructions: str = "",
    count: int = 1,
    style_variant: StyleVariant | None = None,
) -> AsyncIterator[StreamChunk]:
    """Generate rewritten alternatives for a text selection.

    Constructs the PromptContext directly (not via
    ``_build_prompt_context``) because rewrite has unique variables
    (``selection_text``, ``context_before``, ``context_after``,
    ``rewrite_mode_instructions``, ``style_variant_instructions``, ``count``)
    that are not part of the standard context assembly pipeline.
    """
    mode_instr = get_rewrite_mode_instructions(
        rewrite_mode,
        custom_instructions=custom_instructions,
    )

    tone_instr = pipeline._tone_instructions(context.tone)  # pyright: ignore[reportPrivateUsage]

    # Extra variables for prompt template rendering
    extra: dict[str, str] = {
        "user_id": str(request.user_id),
        "project_id": str(request.project_id),
        "chapter_outline": context.chapter_outline,
        "kb_characters": context.kb_characters,
        "kb_locations": context.kb_locations,
        "recent_chapters": context.recent_chapters,
        "character_voice_profiles": context.character_voice_profiles,
        "tone_instructions": tone_instr,
        "writing_language": context.writing_language,
        # Rewrite-specific variables
        "selection_text": selection_text,
        "context_before": context_before,
        "context_after": context_after,
        "rewrite_mode_instructions": mode_instr,
        # CR-AUFG-07-22: style-variant creative direction. Empty string when
        # no variant is requested → template renders nothing (backward compat).
        "style_variant_instructions": get_style_variant_instructions(style_variant),
        "count": str(count),
        # Backward compatibility: chapter_content maps to selection_text
        "chapter_content": selection_text,
    }

    if rewrite_mode == "custom" and custom_instructions:
        extra["custom_instructions"] = custom_instructions

    # Construct PromptContext directly — mode="rewrite_selection" drives
    # the composer to resolve the rewrite prompt template.
    prompt_ctx = PromptContext(
        language=context.language,
        writing_language=context.writing_language,
        project_title=context.project_title,
        genre=context.genre,
        tone=context.tone,
        mode="rewrite_selection",
        existing_content=selection_text,
        author_instructions=request.prompt or request.outline or "",
        user_preferences=context.user_preferences,
        avoidance_patterns=context.avoidance_patterns,
        character_voice_profiles=context.character_voice_profiles,
        author_voice=context.author_voice,
        extra=extra,
    )

    # Compose prompt via RULE-02
    prompt = await pipeline._build_and_validate_prompt(  # pyright: ignore[reportPrivateUsage]
        LLMIntent.REWRITE,
        prompt_ctx,
        user_id=request.user_id,
        project_id=request.project_id,
    )

    # Stream from LLM via RULE-01b
    accumulated: list[str] = []
    async for chunk in pipeline._registry.stream(  # pyright: ignore[reportPrivateUsage]
        intent=LLMIntent.REWRITE,
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
            )
            yield StreamChunk(text=final_text, is_final=True, usage=chunk.usage)
        else:
            accumulated.append(chunk.text)
            yield chunk
