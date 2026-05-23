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

from pydantic_ai import RunContext  # noqa: TC002 — needed at runtime by pydantic_ai internals

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
            output_type=[self._process_summary, SummaryOutput],
            system_prompt=system_prompt,
        )

    async def _process_summary(
        self,
        ctx: RunContext[SummaryDeps],
        summary: str = "",
        key_points: list[str] | None = None,
        word_count: int = 0,
    ) -> SummaryOutput:
        """Output Function — strukturiert die LLM-Response in SummaryOutput.

        Bei Streaming (``ctx.partial_output``) wird nur ein Minimalergebnis zurückgegeben.
        """
        if ctx.partial_output:
            return SummaryOutput()

        return SummaryOutput(
            summary=summary,
            key_points=key_points or [],
            word_count=word_count or len(summary.split()),
        )

    async def run(
        self,
        prompt: str,
        deps: SummaryDeps,
        **kwargs: Any,
    ) -> SummaryOutput:
        """Execute the summary agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]
