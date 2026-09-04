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

from pydantic_ai import (
    ModelRetry,
    RunContext,
)

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.timeline_types import (
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
            output_type=TimelineOutput,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[TimelineDeps],
        output: TimelineOutput,
    ) -> TimelineOutput:
        """Validate deterministic invariants for timeline output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - Each event must have non-empty event_name and description
        - chapter_reference non-empty for each event (traceability)
        - No duplicate events (same event_name + timestamp)
        - Filter out events with empty event_name
        """
        # Filter out events with empty event_name
        valid_events = [e for e in output.timeline_events if e.event_name.strip()]

        for event in valid_events:
            # Each event must have non-empty description
            if not event.description.strip():
                raise ModelRetry(
                    f"Timeline event '{event.event_name}' must have a non-empty description"
                )

            # chapter_reference must be non-empty for traceability
            if not event.chapter_reference.strip():
                raise ModelRetry(
                    f"Timeline event '{event.event_name}' must have "
                    "a non-empty chapter_reference for traceability"
                )

        # Check for duplicates (same event_name + timestamp)
        seen: set[tuple[str, str]] = set()
        for event in valid_events:
            key = (event.event_name.strip(), event.timestamp.strip())
            if key in seen:
                raise ModelRetry(
                    f"Duplicate timeline event: '{event.event_name}' "
                    f"at timestamp '{event.timestamp}'"
                )
            seen.add(key)

        return output.model_copy(update={"timeline_events": valid_events})

    async def run(
        self,
        prompt: str,
        deps: TimelineDeps,
        **kwargs: Any,
    ) -> TimelineOutput:
        """Execute the timeline agent and return structured output."""
        return await super().run(prompt, deps, **kwargs)
