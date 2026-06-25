"""Co-author generation mode — track-changes-style AI revision with diff.

Follows the exact pattern of ``pipeline_rewrite.py`` with these differences:

1. Focus-area instructions instead of rewrite-mode instructions
2. ``LLMIntent.CO_AUTHOR`` instead of ``LLMIntent.REWRITE``
3. Mode ``"co_author"`` instead of ``"rewrite_selection"``
4. After streaming completes, computes diff via :mod:`change_engine`
5. Diff metadata sent in the final chunk's ``context_meta``

See ADR-023 for design decisions.
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
# Focus area instructions — injected into prompt template
# ---------------------------------------------------------------------------

_CO_AUTHOR_FOCUS_INSTRUCTIONS: dict[str, str] = {
    "word_choice": (
        "Look for weak verbs, imprecise nouns, and redundancies. Replace them "
        "with stronger, more specific alternatives. Keep the sentence structure "
        "intact — only change individual words and phrases."
    ),
    "sentence": (
        "Vary sentence structure for better rhythm. Fix awkward phrasing. "
        "Adjust pacing through sentence length variation. Restructure when "
        "it improves clarity, but preserve the author's intended meaning."
    ),
    "dialogue": (
        "Make dialogue more natural and character-appropriate. Remove "
        "on-the-nose lines. Add subtext. Ensure each character has a "
        "distinct voice. Keep the scene's dramatic purpose intact."
    ),
    "description": (
        "Add sensory details where appropriate. Show instead of tell. "
        "Create vivid imagery without overwriting. Match the descriptive "
        "density to the scene's pacing and tone."
    ),
}


def get_co_author_focus_instructions(focus: list[str]) -> str:
    """Build combined focus-area instructions for the prompt template.

    Args:
        focus: List of focus areas selected by the user.

    Returns:
        Combined instructions string for prompt template rendering.
    """
    instructions: list[str] = []
    for area in focus:
        if area in _CO_AUTHOR_FOCUS_INSTRUCTIONS:
            instructions.append(f"### {area}\n{_CO_AUTHOR_FOCUS_INSTRUCTIONS[area]}")
    return "\n\n".join(instructions)


# ---------------------------------------------------------------------------
# Streaming co-author
# ---------------------------------------------------------------------------


async def stream_coauthor(
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
    focus: list[str] | None = None,
    style_variant: StyleVariant | None = None,
    language: str = "en",
) -> AsyncIterator[StreamChunk]:
    """Generate co-author revision with server-side diff computation.

    Constructs the PromptContext directly (not via
    ``_build_prompt_context``) because co-author has unique variables
    (``selection_text``, ``context_before``, ``context_after``,
    ``co_author_focus_instructions``, ``style_variant_instructions``) that
    are not part of the standard context assembly pipeline.

    Args:
        pipeline: The writing pipeline instance.
        request: The generation request.
        context: Assembled writing context.
        config: Resolved model configuration.
        api_key: Optional API key override.
        base_url: Optional base URL override.
        selection_text: The passage selected for improvement.
        context_before: Text immediately before the selection.
        context_after: Text immediately after the selection.
        focus: User-selected focus areas (word_choice, sentence,
            dialogue, description).
        style_variant: Optional creative-direction variant for style-variant
            regeneration (CR-AUFG-07-22).  When set, the variant's
            instruction text is injected into the co-author prompt via
            ``{{style_variant_instructions}}``.  ``None`` renders the variable
            as empty (backward compatible).
        language: Output language code.

    Yields:
        StreamChunk instances — intermediate text chunks during
        streaming, then a final chunk with diff metadata in
        ``context_meta``.
    """
    focus_list = focus or []
    focus_instr = get_co_author_focus_instructions(focus_list)

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
        "writing_language": language,
        # Co-author-specific variables
        "selection_text": selection_text,
        "context_before": context_before,
        "context_after": context_after,
        "co_author_focus_instructions": focus_instr,
        # CR-AUFG-07-22: style-variant creative direction. Empty string when
        # no variant is requested → template renders nothing (backward compat).
        "style_variant_instructions": get_style_variant_instructions(style_variant),
        # Backward compatibility: chapter_content maps to selection_text
        "chapter_content": selection_text,
    }

    # Construct PromptContext with mode="co_author" — drives the
    # composer to resolve the co_author prompt template.
    prompt_ctx = PromptContext(
        language=context.language,
        writing_language=language,
        project_title=context.project_title,
        genre=context.genre,
        tone=context.tone,
        mode="co_author",
        existing_content=selection_text,
        author_instructions=request.prompt or request.outline or "",
        user_preferences=context.user_preferences,
        avoidance_patterns=context.avoidance_patterns,
        character_voice_profiles=context.character_voice_profiles,
        extra=extra,
    )

    # Compose prompt via RULE-02
    prompt = await pipeline._build_and_validate_prompt(  # pyright: ignore[reportPrivateUsage]
        LLMIntent.CO_AUTHOR,
        prompt_ctx,
        user_id=request.user_id,
        project_id=request.project_id,
    )

    # Stream from LLM via RULE-01b
    accumulated: list[str] = []
    async for chunk in pipeline._registry.stream(  # pyright: ignore[reportPrivateUsage]
        intent=LLMIntent.CO_AUTHOR,
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

            # Compute diff after stream completes
            # Lazy import to avoid circular dependency at module level
            from narrare_core.writing.change_engine import DiffResult, compute_changes

            diff_result: DiffResult = compute_changes(
                original=selection_text,
                revised=final_text,
                focus_areas=focus_list,
            )

            # Generate reasoning from diff_result.changes
            if not diff_result.changes:
                reasoning = "No significant changes detected."
            else:
                type_counts: dict[str, int] = {}
                for change in diff_result.changes:
                    ctype = change.change_type
                    type_counts[ctype] = type_counts.get(ctype, 0) + 1

                # Human-readable labels for each change type
                type_display: dict[str, str] = {
                    "word_choice": "word choice changes",
                    "sentence": "sentence restructuring",
                    "dialogue": "dialogue improvements",
                    "description": "descriptive improvements",
                }

                parts: list[str] = []
                for ctype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
                    display = type_display.get(ctype, f"{ctype} changes")
                    parts.append(f"{count} {display}")

                total = diff_result.total_changes
                noun = "improvement" if total == 1 else "improvements"
                reasoning = f"Made {total} {noun}: {', '.join(parts)}."

            # Build context_meta with diff data
            meta: dict[str, object] = {
                "changes": [
                    {
                        "original_text": g.original_text,
                        "revised_text": g.revised_text,
                        "change_type": g.change_type,
                        "index": g.index,
                    }
                    for g in diff_result.changes
                ],
                "total_changes": diff_result.total_changes,
                "has_changes": diff_result.has_changes,
                "reasoning": reasoning,
            }

            yield StreamChunk(
                text=final_text,
                is_final=True,
                usage=chunk.usage,
                context_meta=meta,
            )
        else:
            accumulated.append(chunk.text)
            yield chunk
