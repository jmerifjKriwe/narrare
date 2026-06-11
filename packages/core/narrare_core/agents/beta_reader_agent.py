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

from typing import Any, cast

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.beta_reader_processors import (
    process_beta_reader_phase1,
    process_beta_reader_phase2,
)
from narrare_core.agents.beta_reader_types import (
    BetaReaderDeps,
    BetaReaderPhase1Output,
    BetaReaderPhase2Output,
)
from narrare_core.agents.beta_reader_validators import (
    validate_beta_reader_phase1,
    validate_beta_reader_phase2,
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
            output_type=[process_beta_reader_phase1, BetaReaderPhase1Output],
            system_prompt=system_prompt,
        )
        self._agent.output_validator(validate_beta_reader_phase1)

    async def run_phase1(
        self,
        prompt: str,
        deps: BetaReaderDeps,
        **kwargs: Any,
    ) -> BetaReaderPhase1Output:
        """Execute Phase 1 analysis (full chapter feedback)."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return cast("BetaReaderPhase1Output", result.output)

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
            output_type=[process_beta_reader_phase2, BetaReaderPhase2Output],
            system_prompt=system_prompt,
        )
        phase2_agent._agent.output_validator(validate_beta_reader_phase2)
        result = await phase2_agent.run(prompt, deps=deps)
        return result

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
