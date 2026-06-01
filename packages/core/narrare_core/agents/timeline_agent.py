"""TimelineAgent — NarrareAgent for narrative timeline analysis.

Usage:
    model = await registry.get_model(config)
    agent = TimelineAgent(model=model)
    deps = TimelineDeps(
        genre="Fantasy",
        language="en",
    )
    result = await agent.run(
        prompt="Analyse the timeline for chapters 1-5.",
        deps=deps,
    )
    print(result.timeline_events)
    print(result.temporal_conflicts)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import RunContext  # noqa: TC002 — needed at runtime by pydantic_ai internals

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.timeline_types import (
    TimelineEvent,
    TimelineOutput,
)

if TYPE_CHECKING:
    from narrare_core.writing.context_assembler import WritingContextAssembler


class TimelineDeps:
    """Dependencies for TimelineAgent.

    Attributes:
        genre: Story genre (e.g. "Fantasy", "Sci-Fi").
        language: Output language code.
        context_assembler: Optional context provider for additional context.
    """

    def __init__(
        self,
        genre: str = "",
        language: str = "en",
        context_assembler: WritingContextAssembler | None = None,
    ) -> None:
        self.genre = genre
        self.language = language
        self.context_assembler = context_assembler


class TimelineAgent(NarrareAgent[TimelineDeps, TimelineOutput]):
    """Agent for narrative timeline analysis.

    Takes chapter summaries and entity events, produces a chronological
    timeline with causal connections, temporal conflicts, and coverage gaps.
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=TimelineDeps,
            output_type=[self._process_output, TimelineOutput],
            system_prompt=system_prompt,
        )

    async def _process_output(
        self,
        ctx: RunContext[TimelineDeps],
        timeline_events: list[dict[str, Any]] | None = None,
        temporal_conflicts: list[str] | None = None,
        coverage_gaps: list[str] | None = None,
        overall_assessment: str | None = None,
    ) -> TimelineOutput:
        """Output Function — strukturiert die LLM-Response in TimelineOutput.

        Bei Streaming (``ctx.partial_output``) wird nur ein Minimalergebnis zurückgegeben.
        """
        if ctx.partial_output:
            return TimelineOutput()

        return TimelineOutput(
            timeline_events=[TimelineEvent(**e) for e in (timeline_events or [])],
            temporal_conflicts=temporal_conflicts or [],
            coverage_gaps=coverage_gaps or [],
            overall_assessment=overall_assessment or "",
        )

    async def run(
        self,
        prompt: str,
        deps: TimelineDeps,
        **kwargs: Any,
    ) -> TimelineOutput:
        """Execute the timeline agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]
