"""Prompt building helpers and shared utilities for WritingGraph steps.

Extracted from writing_graph.py to respect the 200-line limit (RULE-04).
Contains:
- Prompt building functions for each graph step
- Shared helpers (_save_state, _get_model)

See CONSTRAINTS.md RULE-02 (all prompts from PromptComposer).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from narrare_core.agents.writing_graph_types import Approved, NeedsRevision
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from pydantic_graph import StepContext

    from narrare_core.agents.writing_graph_types import WritingDeps, WritingState
    from narrare_core.prompts.composer import ComposedPrompt


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


async def get_review_prompt(
    composer: Any,
    deps: WritingDeps,
    state: WritingState,
    word_count: int,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the review_draft step."""
    draft_text = state.draft or ""

    if composer is None:
        review_prompt = (
            f"Review the following draft text.\n"
            f"Genre: {deps.genre}\n"
            f"Tone: {deps.tone}\n"
            f"Target word count: {deps.word_target}\n"
            f"Actual word count: {word_count}\n"
            f"Draft:\n{draft_text}\n"
        )
        return ("", review_prompt)

    context = _base_context(deps, state)
    context.mode = "review"
    context.extra = {
        "word_target": str(deps.word_target or ""),
        "word_count": str(word_count),
    }

    composed: ComposedPrompt = await composer.build(
        LLMIntent.BETA_READ,
        context,
        user_prompt=draft_text,
    )
    return (composed.system, composed.user)


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
