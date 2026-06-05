"""BetaReaderAgent output functions — LLM response structuring.

These are pydantic-ai output functions (tool-like) that transform
raw LLM response dicts into validated Pydantic models.

Phase 1: Full chapter analysis across all categories.
Phase 2: Deep-dive on a specific category with revision suggestions.

Usage:
    from narrare_core.agents.beta_reader_processors import (
        process_beta_reader_phase1,
        process_beta_reader_phase2,
    )

    # Register as output function:
    # agent = Agent(model, output_type=[process_beta_reader_phase1, BetaReaderPhase1Output])
"""

from __future__ import annotations

from typing import Any

# RunContext must be at runtime — pydantic-ai calls get_type_hints()
# on output functions passed via output_type= (TC002 suppressed)
from pydantic_ai import RunContext  # noqa: TC002

from narrare_core.agents.beta_reader_types import (
    AgentDeepDiveFeedback,
    AgentFeedbackItem,
    AgentOverallAssessment,
    AgentReaderQuestion,
    AgentStrength,
    BetaReaderDeps,
    BetaReaderPhase1Output,
    BetaReaderPhase2Output,
)


async def process_beta_reader_phase1(
    ctx: RunContext[BetaReaderDeps],
    strengths: list[dict[str, Any]] | None = None,
    feedback: list[dict[str, Any]] | None = None,
    questions: list[dict[str, Any]] | None = None,
    overall: dict[str, Any] | None = None,
) -> BetaReaderPhase1Output:
    """Output function for Phase 1 — structures LLM response.

    During streaming (ctx.partial_output), returns minimal result.
    """
    if ctx.partial_output:
        return BetaReaderPhase1Output(
            strengths=[],
            feedback=[],
            questions=[],
            overall=AgentOverallAssessment(
                summary="",
                reader_engagement=5,
                emotional_impact=5,
                pacing_score=5,
                prose_quality=5,
                plot_progression=5,
                character_development=5,
            ),
        )

    parsed_strengths = [AgentStrength(**s) for s in (strengths or [])]
    parsed_feedback = [AgentFeedbackItem(**f) for f in (feedback or [])]
    parsed_questions = [AgentReaderQuestion(**q) for q in (questions or [])]
    parsed_overall = AgentOverallAssessment(
        **(
            overall
            or {
                "summary": "",
                "reader_engagement": 5,
                "emotional_impact": 5,
                "pacing_score": 5,
                "prose_quality": 5,
                "plot_progression": 5,
                "character_development": 5,
            }
        ),
    )

    return BetaReaderPhase1Output(
        strengths=parsed_strengths,
        feedback=parsed_feedback,
        questions=parsed_questions,
        overall=parsed_overall,
    )


async def process_beta_reader_phase2(
    ctx: RunContext[BetaReaderDeps],
    detailed_feedback: list[dict[str, Any]] | None = None,
    revision_suggestions: list[str] | None = None,
    category_score: int = 5,
) -> BetaReaderPhase2Output:
    """Output function for Phase 2 — structures deep-dive response.

    During streaming (ctx.partial_output), returns minimal result.
    """
    if ctx.partial_output:
        return BetaReaderPhase2Output(
            detailed_feedback=[],
            revision_suggestions=[],
            category_score=5,
        )

    parsed = [AgentDeepDiveFeedback(**f) for f in (detailed_feedback or [])]
    return BetaReaderPhase2Output(
        detailed_feedback=parsed,
        revision_suggestions=revision_suggestions or [],
        category_score=min(max(category_score, 1), 10),
    )
