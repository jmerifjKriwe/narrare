"""WritingGraph — Pydantic Graph für den Writing-Workflow.

Modelliert den kreativen Schreibprozess als Zustandsmaschine:

    plan_outline → write_draft → review_draft → finalize
                                    ↑       ↓
                                    └─ revise_draft

Verwendet die GraphBuilder API (pydantic-graph 1.97+).
Siehe ADR-015 Phase 4.
"""

from __future__ import annotations

from typing import Any

from pydantic_graph import End, GraphBuilder, StepContext, TypeExpression

from narrare_core.agents.draft_agent import DraftAgent, DraftDeps
from narrare_core.agents.writing_graph_types import (
    Approved,
    NeedsRevision,
    WritingDeps,
    WritingState,
    WritingStatus,
)

# Re-export types for convenience
__all__ = [
    "Approved",
    "NeedsRevision",
    "WritingDeps",
    "WritingState",
    "WritingStatus",
    "build_writing_graph",
    "create_writing_graph",
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _get_model(deps: WritingDeps) -> Any:
    """Hole Model aus der Registry."""
    return await deps.registry.get_model(
        deps.model_config,
        api_key=deps.api_key,
        base_url=deps.base_url,
    )


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------


def build_writing_graph() -> GraphBuilder:
    """Erstelle den Writing-Graphen mit allen Steps + Edges.

    Returns:
        GraphBuilder (noch nicht gebuildet — build() wird vor run() aufgerufen).
    """
    g = GraphBuilder(
        name="writing-graph",
        state_type=WritingState,
        output_type=WritingState,
        deps_type=WritingDeps,
    )

    @g.step
    async def plan_outline(ctx: StepContext[WritingState, WritingDeps, None]) -> None:
        """Erstelle Outline aus dem vorhandenem Kontext."""
        if ctx.deps.chapter_outline:
            ctx.state.outline = ctx.deps.chapter_outline
        else:
            ctx.state.outline = "Chapter " + ctx.state.chapter_id + " outline"
        ctx.state.status = WritingStatus.OUTLINED

    @g.step
    async def write_draft(ctx: StepContext[WritingState, WritingDeps, None]) -> None:
        """Generiere Draft via DraftAgent."""
        model = await _get_model(ctx.deps)
        agent = DraftAgent(model=model, word_target=ctx.deps.word_target)
        parts = [
            "Write chapter " + ctx.state.chapter_id,
            "Genre: " + ctx.deps.genre,
            "Tone: " + ctx.deps.tone,
        ]
        if ctx.state.outline:
            parts.append("Outline:\n" + ctx.state.outline)
        if ctx.deps.chapter_content:
            parts.append("Existing content:\n" + ctx.deps.chapter_content)
        instruction = "\n".join(parts)
        deps = DraftDeps(context_assembler=ctx.deps.context_assembler)
        result = await agent.run(prompt=instruction, deps=deps)
        ctx.state.draft = result.text
        ctx.state.status = WritingStatus.DRAFTED

    @g.step
    async def review_draft(
        ctx: StepContext[WritingState, WritingDeps, None],
    ) -> Approved | NeedsRevision:
        """Review den Draft — gibt Approved oder NeedsRevision zurück."""
        word_count = len(ctx.state.draft.split()) if ctx.state.draft else 0
        target = ctx.deps.word_target

        if ctx.state.attempts >= 3:
            return Approved()

        if target and word_count < int(target * 0.5):
            ctx.state.attempts += 1
            return NeedsRevision(
                feedback="Draft too short ("
                + str(word_count)
                + " words, expected ~"
                + str(target)
                + ").",
            )

        if target and word_count < int(target * 0.8) and ctx.state.attempts < 1:
            ctx.state.attempts += 1
            return NeedsRevision(
                feedback="Good start ("
                + str(word_count)
                + " words), target is ~"
                + str(target)
                + ".",
            )

        return Approved()

    @g.step
    async def revise_draft(
        ctx: StepContext[WritingState, WritingDeps, NeedsRevision],
    ) -> None:
        """Überarbeite den Draft basierend auf Feedback."""
        ctx.state.feedback = ctx.inputs.feedback
        model = await _get_model(ctx.deps)
        agent = DraftAgent(model=model, word_target=ctx.deps.word_target)
        instruction = "Revise based on feedback: " + ctx.state.feedback + "\n\n" + ctx.state.draft
        deps = DraftDeps(context_assembler=ctx.deps.context_assembler)
        result = await agent.run(prompt=instruction, deps=deps)
        ctx.state.revision = result.text
        ctx.state.draft = result.text
        ctx.state.status = WritingStatus.REVISED

    @g.step
    async def finalize(
        ctx: StepContext[WritingState, WritingDeps, Approved],
    ) -> End[WritingState]:
        """Finalisiere den Output und beende den Graph."""
        ctx.state.final = ctx.state.revision or ctx.state.draft
        ctx.state.status = WritingStatus.COMPLETED
        return End(ctx.state)

    # Edges
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
        g.edge_from(finalize).to(g.end_node),
    )

    return g


def create_writing_graph():
    """Convenience: Build und return den Writing-Graph.

    Usage::

        graph = create_writing_graph()
        result = await graph.run(state=WritingState(...), deps=WritingDeps(...))
        final_state = result.data  # WritingState
    """
    return build_writing_graph().build()
