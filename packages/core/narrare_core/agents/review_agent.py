"""ReviewAgent — NarrareAgent für Draft-Review und Qualitätsbewertung.

Usage:
    model = await registry.get_model(config)
    agent = ReviewAgent(model=model)
    deps = ReviewDeps(word_target=2000)
    result = await agent.run(
        prompt="Review this draft:\n\n...draft text...",
        deps=deps,
    )
    print(result.approved, result.feedback)
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext  # noqa: TC002 — needed at runtime by pydantic_ai internals

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.review_types import ReviewOutput


class ReviewDeps:
    """Dependencies for ReviewAgent.

    Attributes:
        word_target: Optional target word count for length check.
    """

    def __init__(self, word_target: int | None = None) -> None:
        self.word_target = word_target


class ReviewAgent(NarrareAgent[ReviewDeps, ReviewOutput]):
    """Agent für Draft-Review und Qualitätsbewertung.

    Analysiert einen Draft auf Qualität, Struktur, Stil und Inhalt.
    Gibt strukturiertes Feedback mit Bewertung und Verbesserungsvorschlägen.
    """

    def __init__(self, model: Any) -> None:
        super().__init__(
            model=model,
            deps_type=ReviewDeps,
            output_type=[self._process_review, ReviewOutput],
            system_prompt=(
                "You are a professional writing critic and editor. "
                "Review the provided draft text and give structured feedback. "
                "Consider: pacing, character voice, dialogue, description quality, "
                "plot coherence, and stylistic consistency with the genre."
            ),
        )

    async def _process_review(
        self,
        ctx: RunContext[ReviewDeps],
        approved: bool = False,
        feedback: str = "",
        suggestions: list[str] | None = None,
        quality_score: int = 5,
        issues: list[str] | None = None,
    ) -> ReviewOutput:
        """Output Function — strukturiert die LLM-Response in ReviewOutput.

        Bei Streaming (``ctx.partial_output``) wird nur ein Minimalergebnis zurückgegeben.
        """
        if ctx.partial_output:
            return ReviewOutput()

        return ReviewOutput(
            approved=approved,
            feedback=feedback,
            suggestions=suggestions or [],
            quality_score=quality_score,
            issues=issues or [],
        )

    async def run(
        self,
        prompt: str,
        deps: ReviewDeps,
        **kwargs: Any,
    ) -> ReviewOutput:
        """Execute the review agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]
