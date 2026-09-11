"""ChapterSummaryAgent — NarrareAgent für Kapitel-Zusammenfassungen.

Usage:
    model = await registry.get_model(config)
    agent = ChapterSummaryAgent(model=model)
    deps = SummaryDeps(
        language="en",
        genre="Fantasy",
        chapter_title="The Hero's Awakening",
    )
    result = await agent.run(
        prompt="Summarize chapter 4:\n\nContent...",
        deps=deps,
    )
    print(result.summary)
    print(result.key_points)
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import (
    ModelRetry,
    RunContext,
)

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.summary_types import SummaryOutput


class SummaryDeps:
    """Dependencies for ChapterSummaryAgent.

    Attributes:
        language: Output language code (default "en").
        genre: Story genre (e.g. "Fantasy").
        chapter_title: Title of the chapter being summarized.
        max_sentences: Maximum number of sentences in the summary (default 4).
    """

    def __init__(
        self,
        language: str = "en",
        genre: str = "",
        chapter_title: str = "",
        max_sentences: int = 4,
    ) -> None:
        self.language = language
        self.genre = genre
        self.chapter_title = chapter_title
        self.max_sentences = max_sentences


class ChapterSummaryAgent(NarrareAgent[SummaryDeps, SummaryOutput]):
    """Agent for generating chapter summaries.

    Takes chapter content + metadata, produces concise 2-4 sentence summary
    with key narrative points.
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=SummaryDeps,
            output_type=SummaryOutput,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[SummaryDeps],
        output: SummaryOutput,
    ) -> SummaryOutput:
        """Validate deterministic invariants for summary output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - summary must be non-empty
        - key_points should have non-empty strings (filter empty)
        - At least one key_point when summary is non-empty
        """
        # summary must be non-empty
        if not output.summary.strip():
            raise ModelRetry(
                "Summary text must be non-empty — every chapter summary requires content"
            )

        # Filter empty key points
        filtered_points = [p for p in output.key_points if p.strip()]

        # At least one key_point when summary is non-empty
        if not filtered_points:
            raise ModelRetry("At least one key_point is required when a summary is provided")

        return output.model_copy(update={"key_points": filtered_points})

    async def run(
        self,
        prompt: str,
        deps: SummaryDeps,
        **kwargs: Any,
    ) -> SummaryOutput:
        """Execute the summary agent and return structured output."""
        return await super().run(prompt, deps, **kwargs)
