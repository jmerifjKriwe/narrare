"""Prompt building helpers and shared utilities for WritingGraph steps.

Extracted from writing_graph.py to respect the 200-line limit (RULE-04).
Contains:
- Prompt building functions for each graph step
- Shared helpers (save_state, get_model)
- Context assembly helper for enriched review

See CONSTRAINTS.md RULE-02 (all prompts from PromptComposer).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from narrare_core.agents.writing_graph_types import Approved, NeedsRevision
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from pydantic_graph import StepContext

    from narrare_core.agents.writing_graph_types import WritingDeps, WritingState
    from narrare_core.prompts.composer import ComposedPrompt
    from narrare_core.writing.models import WritingContext

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def save_state(ctx: StepContext[WritingState, WritingDeps, Any]) -> None:
    """Save state checkpoint if store is configured."""
    if ctx.deps.store is not None and ctx.deps.run_id:
        await ctx.deps.store.save(ctx.deps.run_id, ctx.state)


async def get_model(deps: WritingDeps) -> Any:
    """Resolve model from the registry."""
    return await deps.registry.get_model(
        deps.model_config,
        api_key=deps.api_key,
        base_url=deps.base_url,
    )


# ---------------------------------------------------------------------------
# Prompt context builder
# ---------------------------------------------------------------------------


def _base_context(deps: WritingDeps, state: WritingState) -> PromptContext:
    """Build base PromptContext with fields common to all steps."""
    return PromptContext(
        language=deps.language,
        writing_language=deps.writing_language,
        genre=deps.genre,
        tone=deps.tone,
        project_title="",
        chapter_title=state.outline[:100] if state.outline else "",
    )


async def get_outline_prompt(
    composer: Any,
    deps: WritingDeps,
    state: WritingState,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the plan_outline step.

    Uses PromptComposer when available; falls back to inline prompt.
    """
    if composer is None:
        instruction = (
            f"Create a chapter outline for chapter {state.chapter_id}.\n"
            f"Genre: {deps.genre}\n"
            f"Tone: {deps.tone}\n"
            f"Writing language: {deps.writing_language}\n"
        )
        if deps.chapter_content:
            instruction += f"Existing content context:\n{deps.chapter_content[:500]}\n"
        return ("", instruction)

    context = _base_context(deps, state)
    context.mode = "outline"
    if deps.chapter_content:
        context.existing_content = deps.chapter_content[:500]

    composed: ComposedPrompt = await composer.build(LLMIntent.PLAN, context)
    return (composed.system, composed.user)


async def get_draft_prompt(
    composer: Any,
    deps: WritingDeps,
    state: WritingState,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the write_draft step."""
    if composer is None:
        parts = [
            "Write chapter " + state.chapter_id,
            "Genre: " + deps.genre,
            "Tone: " + deps.tone,
        ]
        if state.outline:
            parts.append("Outline:\n" + state.outline)
        if deps.chapter_content:
            parts.append("Existing content:\n" + deps.chapter_content)
        return ("", "\n".join(parts))

    context = _base_context(deps, state)
    context.mode = "new_chapter"
    if state.outline:
        context.author_instructions = state.outline
    if deps.chapter_content:
        context.existing_content = deps.chapter_content
    if deps.word_target:
        context.extra = {"word_target": str(deps.word_target)}

    composed: ComposedPrompt = await composer.build(LLMIntent.WRITE, context)
    return (composed.system, composed.user)


async def _assemble_review_context(
    deps: WritingDeps,
    state: WritingState,
) -> WritingContext | None:
    """Try to assemble WritingContext for enriched review.

    Gracefully returns None if context assembly fails — the review
    proceeds without KB context (better than blocking).  Follows RULE-11
    (no silent failures): errors are logged via structlog.
    """
    if deps.context_assembler is None:
        return None

    if not state.chapter_id or not state.novel_id:
        return None

    try:
        from uuid import UUID

        result = await deps.context_assembler.assemble(
            chapter_id=UUID(state.chapter_id),
            project_id=UUID(state.novel_id),
            mode="full_draft",
        )
        return result  # type: ignore[return-value]
    except Exception as exc:
        logger.warning(
            "review_context_assembly_failed",
            error=str(exc),
            chapter_id=state.chapter_id,
        )
        return None


def _enrich_review_prompt_with_context(
    review_prompt: str,
    writing_context: WritingContext,
) -> str:
    """Append KB context fields to an inline review prompt."""
    if writing_context.kb_characters:
        review_prompt += f"\nCharacters:\n{writing_context.kb_characters}\n"
    if writing_context.kb_locations:
        review_prompt += f"\nLocations:\n{writing_context.kb_locations}\n"
    if writing_context.kb_factions:
        review_prompt += f"\nFactions:\n{writing_context.kb_factions}\n"
    if writing_context.recent_chapters:
        review_prompt += f"\nRecent chapters:\n{writing_context.recent_chapters}\n"
    return review_prompt


def _enrich_prompt_context_with_kb(
    context: PromptContext,
    writing_context: WritingContext,
) -> None:
    """Populate PromptContext.extra with KB data from WritingContext."""
    if writing_context.kb_characters:
        context.extra["kb_characters"] = writing_context.kb_characters
    if writing_context.kb_locations:
        context.extra["kb_locations"] = writing_context.kb_locations
    if writing_context.kb_factions:
        context.extra["kb_factions"] = writing_context.kb_factions
    if writing_context.kb_suggested:
        context.extra["kb_suggested"] = writing_context.kb_suggested
    if writing_context.recent_chapters:
        context.extra["recent_chapters"] = writing_context.recent_chapters
    if writing_context.user_preferences:
        context.extra["user_preferences"] = writing_context.user_preferences


async def get_review_prompt(
    composer: Any,
    deps: WritingDeps,
    state: WritingState,
    word_count: int,
) -> tuple[str, str, WritingContext | None]:
    """Return (system_prompt, user_prompt, writing_context) for the review_draft step.

    Assembles WritingContext from the context_assembler when available
    and enriches the prompt with KB data for consistency checks.
    Returns the assembled context so the caller can pass it to ReviewDeps.
    """
    draft_text = state.draft or ""

    # Assemble KB context — graceful degradation on failure
    writing_context = await _assemble_review_context(deps, state)

    if composer is None:
        review_prompt = (
            f"Review the following draft text.\n"
            f"Genre: {deps.genre}\n"
            f"Tone: {deps.tone}\n"
            f"Target word count: {deps.word_target}\n"
            f"Actual word count: {word_count}\n"
        )
        if writing_context is not None:
            review_prompt = _enrich_review_prompt_with_context(
                review_prompt,
                writing_context,
            )
        review_prompt += f"\nDraft:\n{draft_text}\n"
        return ("", review_prompt, writing_context)

    context = _base_context(deps, state)
    context.mode = "review"
    context.extra = {
        "word_target": str(deps.word_target or ""),
        "word_count": str(word_count),
    }

    if writing_context is not None:
        _enrich_prompt_context_with_kb(context, writing_context)

    composed: ComposedPrompt = await composer.build(
        LLMIntent.BETA_READ,
        context,
        user_prompt=draft_text,
    )
    return (composed.system, composed.user, writing_context)


async def get_revise_prompt(
    composer: Any,
    deps: WritingDeps,
    state: WritingState,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the revise_draft step."""
    revise_content = "Revise based on feedback: " + state.feedback + "\n\n" + state.draft

    if composer is None:
        return ("", revise_content)

    context = _base_context(deps, state)
    context.mode = "new_chapter"
    context.author_instructions = state.feedback
    context.existing_content = state.draft
    if deps.word_target:
        context.extra = {"word_target": str(deps.word_target)}

    composed: ComposedPrompt = await composer.build(
        LLMIntent.REWRITE,
        context,
        user_prompt=revise_content,
    )
    return (composed.system, composed.user)


async def get_summary_prompt(
    composer: Any,
    deps: WritingDeps,
    state: WritingState,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the generate_summary step."""
    content = state.final or state.draft
    chapter_title = state.outline[:100] if state.outline else ""

    if composer is None:
        instruction = (
            f"Summarize chapter {state.chapter_id}.\n"
            f"Genre: {deps.genre}\n"
            f"Writing language: {deps.writing_language}\n"
            f"Chapter title: {chapter_title}\n\n"
            f"Content:\n{content[:3000]}\n"
        )
        return ("", instruction)

    context = _base_context(deps, state)
    context.mode = "summarize"
    context.chapter_title = chapter_title

    composed: ComposedPrompt = await composer.build(
        LLMIntent.SUMMARIZE,
        context,
        user_prompt=content[:3000],
    )
    return (composed.system, composed.user)


# ---------------------------------------------------------------------------
# Edge wiring
# ---------------------------------------------------------------------------


def add_edges(
    g: Any,
    plan_outline: Any,
    write_draft: Any,
    review_draft: Any,
    revise_draft: Any,
    finalize: Any,
    generate_summary: Any,
) -> None:
    """Wire up all edges for the writing graph.

    Extracted from writing_graph.py to respect the 200-line limit (RULE-04).
    """
    from pydantic_graph import TypeExpression

    g.add(
        g.edge_from(g.start_node).to(plan_outline),
        g.edge_from(plan_outline).to(write_draft),
        g.edge_from(write_draft).to(review_draft),
        g.edge_from(review_draft).to(
            g.decision()
            .branch(g.match(TypeExpression[Approved]).label("approved").to(finalize))
            .branch(g.match(TypeExpression[NeedsRevision]).label("needs revision").to(revise_draft))
        ),
        g.edge_from(revise_draft).to(write_draft),
        g.edge_from(finalize).to(generate_summary),
        g.edge_from(generate_summary).to(g.end_node),  # pyright: ignore[reportArgumentType]
    )
