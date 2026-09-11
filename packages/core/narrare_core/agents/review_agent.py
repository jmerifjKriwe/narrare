"""ReviewAgent — NarrareAgent für Draft-Review und Qualitätsbewertung.

Usage:
    model = await registry.get_model(config)
    agent = ReviewAgent(model=model)
    deps = ReviewDeps(word_target=2000, writing_context=writing_context)
    result = await agent.run(
        prompt="Review this draft:\n\n...draft text...",
        deps=deps,
    )
    print(result.approved, result.feedback)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import (
    ModelRetry,
    RunContext,
)

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.review_types import ReviewOutput

if TYPE_CHECKING:
    from narrare_core.writing.models import WritingContext


class ReviewDeps:
    """Dependencies for ReviewAgent.

    Attributes:
        word_target: Optional target word count for length check.
        writing_context: Optional assembled writing context with KB entities,
            recent chapters, and user preferences for enriched review.
    """

    def __init__(
        self,
        word_target: int | None = None,
        writing_context: WritingContext | None = None,
    ) -> None:
        self.word_target = word_target
        self.writing_context = writing_context


class ReviewAgent(NarrareAgent[ReviewDeps, ReviewOutput]):
    """Agent für Draft-Review und Qualitätsbewertung.

    Analysiert einen Draft auf Qualität, Struktur, Stil und Inhalt.
    Gibt strukturiertes Feedback mit Bewertung und Verbesserungsvorschlägen.
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=ReviewDeps,
            output_type=ReviewOutput,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[ReviewDeps],
        output: ReviewOutput,
    ) -> ReviewOutput:
        """Validate deterministic invariants for review output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - quality_score must be 1-10 (enforce bounds)
        - feedback must be non-empty
        - When approved is False, issues must be non-empty
        - Filter empty strings from suggestions and issues lists
        """
        # quality_score bounds enforcement
        score = output.quality_score
        if score < 1 or score > 10:
            raise ModelRetry(f"quality_score must be between 1 and 10, got {score}")

        # feedback must be non-empty
        if not output.feedback.strip():
            raise ModelRetry(
                "Review feedback must be non-empty — the reviewer always provides feedback"
            )

        # Filter empty strings from suggestions and issues
        filtered_suggestions = [s for s in output.suggestions if s.strip()]
        filtered_issues = [i for i in output.issues if i.strip()]

        # When not approved, issues must be non-empty (after filtering)
        if not output.approved and not filtered_issues:
            raise ModelRetry(
                "When the draft is not approved (approved=False), at least one issue must be listed"
            )

        return output.model_copy(
            update={
                "suggestions": filtered_suggestions,
                "issues": filtered_issues,
            }
        )

    async def run(
        self,
        prompt: str,
        deps: ReviewDeps,
        **kwargs: Any,
    ) -> ReviewOutput:
        """Execute the review agent and return structured output."""
        return await super().run(prompt, deps, **kwargs)
