"""BetaReaderAgent output validators — ADR-035.

Deterministic invariants enforced at the agent boundary:

Phase 1:
- Each strength/feedback/question should have non-empty content
- category should be from known set (plot/character/prose/pacing/experience)

Phase 2:
- category_score clamped 1-10
- revision_suggestions should have non-empty strings

Usage:
    from narrare_core.agents.beta_reader_validators import (
        validate_beta_reader_phase1,
        validate_beta_reader_phase2,
    )

    validator = validate_beta_reader_phase1
    # Register: agent._agent.output_validator(validate_beta_reader_phase1)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import ModelRetry

if TYPE_CHECKING:
    from pydantic_ai import RunContext

    from narrare_core.agents.beta_reader_types import (
        AgentFeedbackItem,
        AgentReaderQuestion,
        AgentStrength,
        BetaReaderDeps,
        BetaReaderPhase1Output,
        BetaReaderPhase2Output,
    )

# Known categories for beta reader feedback
VALID_CATEGORIES = frozenset(
    {
        "plot",
        "character",
        "prose",
        "pacing",
        "experience",
    }
)


async def validate_beta_reader_phase1(
    ctx: RunContext[BetaReaderDeps],
    output: BetaReaderPhase1Output,
) -> BetaReaderPhase1Output:
    """Validate deterministic invariants for Phase 1 output.

    ADR-035: Enforces output quality at the agent boundary.
    No side effects — deterministic validation only.

    Invariants:
    - Each strength/feedback/question should have non-empty content
    - category should be from known set (plot/character/prose/pacing/experience)
    """
    # Validate strengths
    valid_strengths: list[AgentStrength] = []
    for s in output.strengths:
        if not s.title.strip() or not s.description.strip():
            continue
        valid_strengths.append(s)

    # Validate feedback
    valid_feedback: list[AgentFeedbackItem] = []
    for f in output.feedback:
        if not f.title.strip() or not f.description.strip():
            continue
        if f.category not in VALID_CATEGORIES:
            raise ModelRetry(
                f"Feedback category '{f.category}' is not valid — "
                f"must be one of {sorted(VALID_CATEGORIES)}"
            )
        valid_feedback.append(f)

    # Validate questions
    valid_questions: list[AgentReaderQuestion] = []
    for q in output.questions:
        if not q.question.strip():
            continue
        valid_questions.append(q)

    return output.model_copy(
        update={
            "strengths": valid_strengths,
            "feedback": valid_feedback,
            "questions": valid_questions,
        }
    )


async def validate_beta_reader_phase2(
    ctx: RunContext[BetaReaderDeps],
    output: BetaReaderPhase2Output,
) -> BetaReaderPhase2Output:
    """Validate deterministic invariants for Phase 2 output.

    ADR-035: Enforces output quality at the agent boundary.
    No side effects — deterministic validation only.

    Invariants:
    - category_score clamped 1-10
    - revision_suggestions should have non-empty strings
    """
    # Filter empty revision suggestions
    valid_suggestions = [s for s in output.revision_suggestions if s.strip()]

    # Clamp category_score to the 1-10 range (the output model does not
    # enforce this itself — the validator is the single clamp point).
    score = max(1, min(10, output.category_score))

    return output.model_copy(
        update={
            "revision_suggestions": valid_suggestions,
            "category_score": score,
        }
    )
