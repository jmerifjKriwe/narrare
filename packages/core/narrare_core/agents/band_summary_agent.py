"""BandSummaryAgent — NarrareAgent für novel-level Band-Zusammenfassungen.

Aggregiert vor-generierte Kapitel-Zusammenfassungen in eine Band-Summary
mit zwei Feldern: ``full_summary`` (Mehrere Absätze) und ``short_summary``
(ein Satz). Diese werden von der SeriesHistoryTier (Spec 2 Task 6) in den
Schreib-Kontext injiziert — full für Bände im recency window, short für
ältere Bände.

Usage::

    model = await registry.get_model(config)
    agent = BandSummaryAgent(model=model)
    deps = BandSummaryDeps(
        novel_title="The Forbidden Vale",
        genre="Fantasy",
        chapter_summaries=[
            "Chapter 1: The hero arrives at the vale.",
            "Chapter 2: A dark secret is revealed.",
        ],
    )
    result = await agent.run(prompt="<composed prompt + chapter summaries>", deps=deps)
    print(result.full_summary)
    print(result.short_summary)

The governed ``analysis/en/band_summary/system.md`` template is resolved by
the Layer-3 service via PromptComposer (RULE-02b). Chapter summaries flow as
runtime content in the agent run prompt (user channel, RULE-02a category 3),
mirroring how coreference / readability / voice receive the analysed passage.
"""

from __future__ import annotations

from typing import Any, cast

from pydantic_ai import (
    ModelRetry,
    RunContext,
)

from narrare_core.agents.band_summary_types import BandSummaryDeps, BandSummaryOutput
from narrare_core.agents.base import NarrareAgent


class BandSummaryAgent(NarrareAgent[BandSummaryDeps, BandSummaryOutput]):
    """Agent for aggregating chapter summaries into a novel-level band summary.

    Takes a novel title, genre, and a list of pre-generated chapter summaries,
    produces a multi-paragraph full summary plus a single-sentence short
    summary. One LLM call, structured output.
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=BandSummaryDeps,
            output_type=[self._process_output, BandSummaryOutput],
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[BandSummaryDeps],
        output: BandSummaryOutput,
    ) -> BandSummaryOutput:
        """Validate deterministic invariants for band-summary output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - full_summary must be non-empty (it is the primary band record)
        - short_summary must be non-empty (one sentence for older bands)
        """
        if not output.full_summary.strip():
            raise ModelRetry(
                "full_summary must be non-empty — every band summary requires a full plot summary"
            )

        if not output.short_summary.strip():
            raise ModelRetry(
                "short_summary must be non-empty — every band summary requires a one-sentence "
                "distillation for older bands outside the recency window"
            )

        return output

    async def _process_output(
        self,
        ctx: RunContext[BandSummaryDeps],
        full_summary: str = "",
        short_summary: str = "",
    ) -> BandSummaryOutput:
        """Output Function — strukturiert die LLM-Response in BandSummaryOutput.

        Bei Streaming (``ctx.partial_output``) wird nur ein Minimalergebnis zurückgegeben.
        """
        if ctx.partial_output:
            return BandSummaryOutput()

        return BandSummaryOutput(full_summary=full_summary, short_summary=short_summary)

    async def run(
        self,
        prompt: str,
        deps: BandSummaryDeps,
        **kwargs: Any,
    ) -> BandSummaryOutput:
        """Execute the band-summary agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return cast("BandSummaryOutput", result.output)
