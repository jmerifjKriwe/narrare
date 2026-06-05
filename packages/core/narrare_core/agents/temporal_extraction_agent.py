"""TemporalExtractionAgent — Extract temporal expressions from chapter content.

Usage::

    model = await registry.get_model(config)
    agent = TemporalExtractionAgent(model=model)
    deps = TemporalExtractionDeps(
        genre="Fantasy",
        language="en",
        existing_events=["Battle of Helm's Deep", "Arrival at Rivendell"],
    )
    result = await agent.run(
        prompt="Extract temporal expressions from the following chapter...",
        deps=deps,
    )
    for expr in result.extracted:
        print(f"{expr.expression}: {expr.event_name} (confidence: {expr.confidence})")
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import (
    ModelRetry,
    RunContext,
)

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.temporal_extraction_types import (
    ExtractedTemporalExpression,
    TemporalExtractionOutput,
)


class TemporalExtractionDeps:
    """Dependencies for TemporalExtractionAgent.

    Attributes:
        genre: Novel genre for context-aware extraction.
        language: Language of the text (``"en"``, ``"de"``, ``"fr"``).
        existing_events: Names of existing timeline events (to avoid duplicates).
    """

    def __init__(
        self,
        genre: str = "",
        language: str = "en",
        existing_events: list[str] | None = None,
    ) -> None:
        self.genre = genre
        self.language = language
        self.existing_events = existing_events or []


class TemporalExtractionAgent(NarrareAgent[TemporalExtractionDeps, TemporalExtractionOutput]):
    """Agent that extracts temporal expressions from chapter content.

    Identifies time references, dates, durations, and temporal markers
    in narrative text. Returns structured extraction results with confidence
    scores for user review.
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=TemporalExtractionDeps,
            output_type=[self._process_output, TemporalExtractionOutput],
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[TemporalExtractionDeps],
        output: TemporalExtractionOutput,
    ) -> TemporalExtractionOutput:
        """Validate deterministic invariants for temporal extraction output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - expression must be non-empty for each extraction
        - Filter extractions with empty expression
        - Confidence bounds enforcement (0.0-1.0)
        """
        # Filter extractions with empty expression
        valid_extractions = [e for e in output.extracted if e.expression.strip()]

        # Enforce confidence bounds on each extraction
        for e in valid_extractions:
            if e.confidence < 0.0 or e.confidence > 1.0:
                raise ModelRetry(
                    f"Temporal expression '{e.expression}' has confidence "
                    f"{e.confidence} — must be between 0.0 and 1.0"
                )

        return output.model_copy(update={"extracted": valid_extractions})

    async def _process_output(
        self,
        ctx: RunContext[TemporalExtractionDeps],
        extracted: list[dict[str, Any]] | None = None,
        chapter_temporal_markers: list[str] | None = None,
        extraction_notes: str | None = None,
    ) -> TemporalExtractionOutput:
        """Output Function — structures the LLM response into TemporalExtractionOutput.

        During streaming (``ctx.partial_output``) returns a minimal empty result.
        """
        if ctx.partial_output:
            return TemporalExtractionOutput()

        return TemporalExtractionOutput(
            extracted=[ExtractedTemporalExpression(**e) for e in (extracted or [])],
            chapter_temporal_markers=chapter_temporal_markers or [],
            extraction_notes=extraction_notes or "",
        )

    async def run(
        self,
        prompt: str,
        deps: TemporalExtractionDeps,
        **kwargs: Any,
    ) -> TemporalExtractionOutput:
        """Execute the temporal extraction agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]
