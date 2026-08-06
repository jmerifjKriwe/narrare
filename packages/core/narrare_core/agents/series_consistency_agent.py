"""SeriesConsistencyAgent — Detects contradictions between novel chapters and Series-Canon KB.

Cross-novel consistency checking: compares the chapter prose of a single band
(novel) against the series **Canon KB** (the cross-novel fixed-facts layer
established in Spec 1). Flags passages that contradict Canon records — e.g.
a chapter describing a character's eye colour differently than Canon, or
naming a ruler that Canon does not record.

This is distinct from the per-novel ``ConsistencyAgent`` (CONS-001), which
checks *within* a novel (chapter vs. KB-entity vs. other chapters).
``SeriesConsistencyAgent`` checks *novel-vs-series-Canon*.

Follows the same pattern as ``BandSummaryAgent`` — ``NarrareAgent`` subclass
with an Output Function for post-processing and an ADR-035 output validator.
One LLM call, structured output. An empty conflicts list means no
contradictions were found.

Usage::

    model = await registry.get_model(config)
    agent = SeriesConsistencyAgent(model=model)
    deps = SeriesConsistencyDeps(
        novel_title="The Forbidden Vale",
        canon_entries=["Canon: Elara has blue eyes.", "Canon: The kingdom is northern."],
        chapter_texts=["Elara's green eyes scanned the horizon.", ...],
    )
    result = await agent.run(prompt="<composed prompt + canon + chapters>", deps=deps)
    for conflict in result.conflicts:
        print(f"[{conflict.severity}] {conflict.explanation}")

The governed ``analysis/en/series_consistency/system.md`` template is resolved
by the Layer-3 service via PromptComposer (RULE-02b). Canon entries + chapter
texts flow as runtime content in the agent run prompt (user channel,
RULE-02a category 3), mirroring how coreference / readability / voice receive
the analysed passage.
"""

from __future__ import annotations

from typing import Any, cast

from pydantic_ai import (
    ModelRetry,
    RunContext,
)

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.series_consistency_types import (
    CanonConflict,
    SeriesConsistencyDeps,
    SeriesConsistencyOutput,
)


class SeriesConsistencyAgent(NarrareAgent[SeriesConsistencyDeps, SeriesConsistencyOutput]):
    """Agent for detecting contradictions between novel chapters and Series-Canon KB.

    Takes a novel title, formatted Canon KB entries, and the chapter texts of
    the band being checked, produces a list of canon conflicts. Each conflict
    names the contradicted Canon entry, quotes the contradicting passage,
    states what Canon says, explains the contradiction, and rates severity.
    One LLM call, structured output. An empty conflicts list means no
    contradictions were found.
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=SeriesConsistencyDeps,
            output_type=[self._process_output, SeriesConsistencyOutput],
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[SeriesConsistencyDeps],
        output: SeriesConsistencyOutput,
    ) -> SeriesConsistencyOutput:
        """Validate deterministic invariants for series-consistency output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - An empty conflicts list is valid (no contradictions found).
        - Filter out conflicts with empty ``explanation`` (silently dropped).
        - Every remaining conflict must have a non-empty ``chapter_text_excerpt``
          (the contradicting passage) and a non-empty ``canon_statement``
          (what Canon says) — a contradiction needs both sides.
        """
        # Filter out conflicts with empty explanations (no usable signal).
        valid_conflicts = [c for c in output.conflicts if c.explanation.strip()]

        for conflict in valid_conflicts:
            if not conflict.chapter_text_excerpt.strip():
                raise ModelRetry(
                    f"Canon conflict '{conflict.explanation[:50]}' must have a non-empty "
                    "chapter_text_excerpt (the contradicting passage from the chapter)"
                )
            if not conflict.canon_statement.strip():
                raise ModelRetry(
                    f"Canon conflict '{conflict.explanation[:50]}' must have a non-empty "
                    "canon_statement (what the Canon entry says)"
                )

        return output.model_copy(update={"conflicts": valid_conflicts})

    async def _process_output(
        self,
        ctx: RunContext[SeriesConsistencyDeps],
        conflicts: list[dict[str, Any]] | None = None,
        summary: str = "",
    ) -> SeriesConsistencyOutput:
        """Output Function — structures the LLM response into SeriesConsistencyOutput.

        During streaming (``ctx.partial_output``), returns a minimal empty result.
        Series-consistency checking is non-streaming by nature, but the output
        function pattern is required for type-safe structured output with pydantic-ai.
        """
        if ctx.partial_output:
            return SeriesConsistencyOutput()

        items: list[CanonConflict] = []
        for conflict in conflicts or []:
            items.append(CanonConflict.model_validate(conflict))

        return SeriesConsistencyOutput(conflicts=items, summary=summary)

    async def run(
        self,
        prompt: str,
        deps: SeriesConsistencyDeps,
        **kwargs: Any,
    ) -> SeriesConsistencyOutput:
        """Execute the series-consistency agent and return structured output.

        Args:
            prompt: The user message / analysis request for the agent. The
                Layer-3 service composes the governed system prompt via
                PromptComposer and supplies the Canon entries + chapter texts
                as runtime content here (user channel).
            deps: Dependencies providing canon entries, chapter texts, and
                novel title.
            **kwargs: Additional arguments passed to pydantic-ai ``run()``.

        Returns:
            Structured output with conflicts (empty = no contradictions) and
            an overall summary.
        """
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return cast("SeriesConsistencyOutput", result.output)
