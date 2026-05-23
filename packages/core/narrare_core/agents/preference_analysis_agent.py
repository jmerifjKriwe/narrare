"""PreferenceAnalysisAgent — analyzes writing preferences from feedback history.

Usage:
    model = await registry.get_model(config)
    agent = PreferenceAnalysisAgent(model=model)
    deps = PreferenceAnalysisDeps(
        language="en",
        genre="Fantasy",
        event_count=42,
        feedback_text="User accepted 30 suggestions about dialogue...",
    )
    result = await agent.run(
        prompt="Analyze the following feedback history for writing preferences.",
        deps=deps,
    )
    print(result.style_patterns)
    print(result.confidence)
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext  # noqa: TC002 — needed at runtime by pydantic_ai internals

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.preference_analysis_types import PreferenceAnalysisOutput


class PreferenceAnalysisDeps:
    """Dependencies for PreferenceAnalysisAgent.

    Attributes:
        language: Output language code (default "en").
        genre: Story genre (e.g. "Fantasy").
        event_count: Number of feedback events being analyzed.
        feedback_text: Aggregated feedback text for analysis.
    """

    def __init__(
        self,
        language: str = "en",
        genre: str = "",
        event_count: int = 0,
        feedback_text: str = "",
    ) -> None:
        self.language = language
        self.genre = genre
        self.event_count = event_count
        self.feedback_text = feedback_text


class PreferenceAnalysisAgent(NarrareAgent[PreferenceAnalysisDeps, PreferenceAnalysisOutput]):
    """Agent for analyzing writing preferences from feedback history.

    Takes aggregated feedback events and produces structured preference
    analysis with style patterns, content patterns, avoidance patterns,
    and confidence scoring.
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=PreferenceAnalysisDeps,
            output_type=[self._process_analysis, PreferenceAnalysisOutput],
            system_prompt=system_prompt,
        )

    async def _process_analysis(
        self,
        ctx: RunContext[PreferenceAnalysisDeps],
        style_patterns: list[str] | None = None,
        content_patterns: list[str] | None = None,
        avoidance_patterns: list[str] | None = None,
        confidence: float = 0.0,
        summary: str = "",
    ) -> PreferenceAnalysisOutput:
        """Output Function — structures the LLM response into PreferenceAnalysisOutput.

        During streaming (``ctx.partial_output``), returns a minimal result.
        """
        if ctx.partial_output:
            return PreferenceAnalysisOutput()

        return PreferenceAnalysisOutput(
            style_patterns=style_patterns or [],
            content_patterns=content_patterns or [],
            avoidance_patterns=avoidance_patterns or [],
            confidence=confidence,
            summary=summary,
        )

    async def run(
        self,
        prompt: str,
        deps: PreferenceAnalysisDeps,
        **kwargs: Any,
    ) -> PreferenceAnalysisOutput:
        """Execute the preference analysis agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]
