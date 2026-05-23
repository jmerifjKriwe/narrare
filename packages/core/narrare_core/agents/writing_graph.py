"""WritingGraph — Pydantic Graph für den Writing-Workflow.

    plan_outline → write_draft → review_draft → finalize
                                    ↑       ↓
                                    └─ revise_draft

Uses GraphBuilder API (pydantic-graph 1.97+). See ADR-015 Phase 4.
"""

from __future__ import annotations

from pydantic_graph import End, GraphBuilder, StepContext

from narrare_core.agents.draft_agent import DraftAgent, DraftDeps
from narrare_core.agents.outline_agent import OutlineAgent, OutlineDeps
from narrare_core.agents.review_agent import ReviewAgent, ReviewDeps
from narrare_core.agents.summary_agent import ChapterSummaryAgent, SummaryDeps
from narrare_core.agents.writing_graph_prompts import (
    add_edges,
    get_draft_prompt,
    get_model,
    get_outline_prompt,
    get_review_prompt,
    get_revise_prompt,
    get_summary_prompt,
    save_state,
)
from narrare_core.agents.writing_graph_types import (
    Approved,
    NeedsRevision,
    WritingDeps,
    WritingState,
    WritingStatus,
)

__all__ = [
    "Approved",
    "NeedsRevision",
    "WritingDeps",
    "WritingState",
    "WritingStatus",
    "build_writing_graph",
]


def build_writing_graph() -> GraphBuilder[WritingState, WritingDeps, None, WritingState]:
    """Erstelle den Writing-Graphen mit allen Steps + Edges."""
    g = GraphBuilder(
        name="writing-graph",
        state_type=WritingState,
        output_type=WritingState,
        deps_type=WritingDeps,
    )

    @g.step
    async def plan_outline(ctx: StepContext[WritingState, WritingDeps, None]) -> None:
        """Erstelle Outline via OutlineAgent."""
        if ctx.deps.chapter_outline:
            ctx.state.outline = ctx.deps.chapter_outline
            ctx.state.status = WritingStatus.OUTLINED
            await save_state(ctx)
            return

        model = await get_model(ctx.deps)
        system_prompt, user_prompt = await get_outline_prompt(
            ctx.deps.composer,
            ctx.deps,
            ctx.state,
        )
        agent = OutlineAgent(model=model, system_prompt=system_prompt or None)
        deps = OutlineDeps(genre=ctx.deps.genre, tone=ctx.deps.tone, language=ctx.deps.language)
        result = await agent.run(prompt=user_prompt, deps=deps)
        ctx.state.outline = result.outline_text or result.chapter_title
        ctx.state.status = WritingStatus.OUTLINED
        await save_state(ctx)

    @g.step
    async def write_draft(ctx: StepContext[WritingState, WritingDeps, None]) -> None:
        """Generiere Draft via DraftAgent."""
        model = await get_model(ctx.deps)
        system_prompt, user_prompt = await get_draft_prompt(
            ctx.deps.composer,
            ctx.deps,
            ctx.state,
        )
        agent = DraftAgent(
            model=model,
            word_target=ctx.deps.word_target,
            system_prompt=system_prompt or None,
        )
        deps = DraftDeps(context_assembler=ctx.deps.context_assembler)
        result = await agent.run(prompt=user_prompt, deps=deps)
        ctx.state.draft = result.text
        ctx.state.status = WritingStatus.DRAFTED
        await save_state(ctx)

    @g.step
    async def review_draft(
        ctx: StepContext[WritingState, WritingDeps, None],
    ) -> Approved | NeedsRevision:
        """Review den Draft via ReviewAgent + word-count Guards."""
        word_count = len(ctx.state.draft.split()) if ctx.state.draft else 0
        target = ctx.deps.word_target

        if ctx.state.attempts >= 3:
            await save_state(ctx)
            return Approved()

        if target and word_count < int(target * 0.5):
            ctx.state.attempts += 1
            await save_state(ctx)
            return NeedsRevision(
                feedback=f"Draft too short ({word_count} words, expected ~{target}).",
            )

        model = await get_model(ctx.deps)
        system_prompt, user_prompt, writing_context = await get_review_prompt(
            ctx.deps.composer,
            ctx.deps,
            ctx.state,
            word_count,
        )
        agent = ReviewAgent(model=model, system_prompt=system_prompt or None)
        rdeps = ReviewDeps(word_target=target, writing_context=writing_context)
        result = await agent.run(prompt=user_prompt, deps=rdeps)

        if not result.approved and ctx.state.attempts < 3:
            ctx.state.attempts += 1
            feedback_parts = [result.feedback]
            if result.suggestions:
                feedback_parts.append("Suggestions:\n- " + "\n- ".join(result.suggestions))
            await save_state(ctx)
            return NeedsRevision(feedback="\n\n".join(feedback_parts))

        await save_state(ctx)
        return Approved()

    @g.step
    async def revise_draft(
        ctx: StepContext[WritingState, WritingDeps, NeedsRevision],
    ) -> None:
        """Überarbeite den Draft basierend auf Feedback."""
        ctx.state.feedback = ctx.inputs.feedback
        model = await get_model(ctx.deps)
        system_prompt, user_prompt = await get_revise_prompt(
            ctx.deps.composer,
            ctx.deps,
            ctx.state,
        )
        agent = DraftAgent(
            model=model,
            word_target=ctx.deps.word_target,
            system_prompt=system_prompt or None,
        )
        deps = DraftDeps(context_assembler=ctx.deps.context_assembler)
        result = await agent.run(prompt=user_prompt, deps=deps)
        ctx.state.revision = result.text
        ctx.state.draft = result.text
        ctx.state.status = WritingStatus.REVISED
        await save_state(ctx)

    @g.step
    async def finalize(
        ctx: StepContext[WritingState, WritingDeps, Approved],
    ) -> None:
        """Finalisiere den Output."""
        ctx.state.final = ctx.state.revision or ctx.state.draft
        ctx.state.status = WritingStatus.COMPLETED
        await save_state(ctx)

    @g.step
    async def generate_summary(
        ctx: StepContext[WritingState, WritingDeps, None],
    ) -> End[WritingState]:
        """Erzeuge Kapitel-Zusammenfassung via ChapterSummaryAgent."""
        if not (ctx.state.final or ctx.state.draft or "").strip():
            ctx.state.status = WritingStatus.SUMMARIZED
            await save_state(ctx)
            return End(ctx.state)

        model = await get_model(ctx.deps)
        system_prompt, user_prompt = await get_summary_prompt(
            ctx.deps.composer,
            ctx.deps,
            ctx.state,
        )
        agent = ChapterSummaryAgent(model=model, system_prompt=system_prompt or None)
        deps = SummaryDeps(
            language=ctx.deps.language,
            genre=ctx.deps.genre,
            chapter_title=ctx.state.outline[:100],
        )
        result = await agent.run(prompt=user_prompt, deps=deps)
        ctx.state.summary = result.summary
        ctx.state.status = WritingStatus.SUMMARIZED
        await save_state(ctx)
        return End(ctx.state)

    add_edges(g, plan_outline, write_draft, review_draft, revise_draft, finalize, generate_summary)
    return g
