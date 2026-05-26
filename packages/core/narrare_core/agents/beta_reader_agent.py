"""BetaReaderAgent — chapter-level beta reader simulation.

Two-phase analysis:
  Phase 1: Full chapter analysis → strengths, feedback, questions, scores
  Phase 2: Category deep-dive → detailed feedback with revision suggestions

Follows the same pattern as worldbuilding_agent.py.

Usage:
    model = await registry.get_model(config)
    agent = BetaReaderAgent(model=model)
    deps = BetaReaderDeps(
        language="en",
        chapter_text="...",
        chapter_titles=["Chapter 1"],
        word_count=3500,
        previous_chapter_summaries=[],
        kb_characters=[{"name": "Alice", "summary": "Protagonist"}],
        kb_locations=[{"name": "Castle", "summary": "Main setting"}],
        genre="Fantasy",
    )
    result = await agent.run_phase1(prompt="Analyze this chapter", deps=deps)
    # result.strengths, result.feedback, result.questions, result.overall

    # Then optionally Phase 2:
    phase2_result = await agent.run_phase2(
        prompt="Deep-dive on character",
        deps=BetaReaderDeps(deepdive_category="character", ...),
        model=model,
    )
    # phase2_result.detailed_feedback, phase2_result.revision_suggestions
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext  # noqa: TC002 — needed at runtime by pydantic_ai internals

from narrare_core.agents.base import NarrareAgent
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


class BetaReaderAgent(NarrareAgent[BetaReaderDeps, BetaReaderPhase1Output]):
    """Agent that simulates a beta reader's feedback.

    Phase 1: Full chapter analysis across all categories.
    Phase 2: Deep-dive on a specific category with revision suggestions.
    """

    def __init__(
        self,
        model: Any,
        system_prompt: str | None = None,
    ) -> None:
        """Initialize BetaReaderAgent.

        Args:
            model: LLM model from ModelRegistry.
            system_prompt: System prompt (composed by PromptComposer).
        """
        super().__init__(
            model=model,
            deps_type=BetaReaderDeps,
            output_type=[self._process_phase1, BetaReaderPhase1Output],
            system_prompt=system_prompt,
        )

    async def _process_phase1(
        self,
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

    async def run_phase1(
        self,
        prompt: str,
        deps: BetaReaderDeps,
        **kwargs: Any,
    ) -> BetaReaderPhase1Output:
        """Execute Phase 1 analysis (full chapter feedback)."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]

    async def run_phase2(
        self,
        prompt: str,
        deps: BetaReaderDeps,
        model: Any,
        system_prompt: str | None = None,
    ) -> BetaReaderPhase2Output:
        """Execute Phase 2 deep-dive with separate agent instance.

        Phase 2 has its own agent instance with different output type
        and potentially different model/system prompt.
        """
        phase2_agent = NarrareAgent[BetaReaderDeps, BetaReaderPhase2Output](
            model=model,
            deps_type=BetaReaderDeps,
            output_type=[self._process_phase2, BetaReaderPhase2Output],
            system_prompt=system_prompt,
        )
        result = await phase2_agent.run(prompt, deps=deps)
        return result.output  # type: ignore[return-value]

    async def _process_phase2(
        self,
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

    async def run(
        self,
        prompt: str,
        deps: BetaReaderDeps,
        **kwargs: Any,
    ) -> BetaReaderPhase1Output:
        """Default run for Phase 1 (backwards compatibility).

        Prefer run_phase1() for explicit clarity.
        """
        return await self.run_phase1(prompt, deps, **kwargs)
