"""FactExtractorAgent — General-purpose fact extraction with provenance.

Stage 1 of the staged consistency pipeline (ADR-044). Extracts structured
``ExtractedFact`` records from chapter prose, KB entity data, and timeline
events. Each fact carries source provenance, confidence, and entity references.

Designed for reuse across features:
- CONS-001: Consistency checking (primary consumer)
- KB-007: Entity extraction from chapters
- ANAL-005: Coreference resolution
- Future: Plot gap detection, worldbuilding expansion

Usage:
    model = await registry.get_model(config)
    agent = FactExtractorAgent(model=model)
    deps = FactExtractorDeps(
        chapter_texts={"ch1": "Anna walked through the forest."},
        kb_entity_names=["Anna", "The Tower"],
        timeline_envelopes=[...],
        language="en",
        genre="Fantasy",
    )
    result = await agent.run(prompt="Extract all facts.", deps=deps)
    for fact in result.facts:
        print(f"[{fact.fact_type}] {fact.subject} {fact.predicate} {fact.object_value}")
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import (
    ModelRetry,
    RunContext,
)

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.fact_extractor_types import (
    FactExtractorDeps,
    FactExtractorOutput,
)


class FactExtractorAgent(NarrareAgent[FactExtractorDeps, FactExtractorOutput]):
    """Agent for extracting structured facts with provenance from prose.

    Extracts ``ExtractedFact`` records from chapter text, KB entity context,
    and timeline events. Each fact carries:
    - Source chapter and exact evidence quote
    - Confidence score (0.0-1.0)
    - Structured subject-predicate-object representation
    - Fact type classification

    Does NOT perform contradiction detection — that is ConsistencyAgent's
    responsibility (Stage 2).
    """

    def __init__(
        self,
        model: Any,
        system_prompt: str | None = None,
    ) -> None:
        """Initialize FactExtractorAgent.

        Args:
            model: LLM model from ModelRegistry.
            system_prompt: Optional system prompt. Built by service layer
                via PromptComposer. NarrareMeta Capability is always active.
        """
        super().__init__(
            model=model,
            deps_type=FactExtractorDeps,
            output_type=FactExtractorOutput,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[FactExtractorDeps],
        output: FactExtractorOutput,
    ) -> FactExtractorOutput:
        """Validate deterministic invariants for fact extraction output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - Every fact must have non-empty subject, predicate, object_value
        - Every fact must have non-empty evidence_text (exact quote)
        - No duplicate facts (same subject + predicate + object_value)
        - Filter out facts with empty required fields
        """
        valid_facts = [
            f
            for f in output.facts
            if f.subject.strip() and f.predicate.strip() and f.object_value.strip()
        ]

        for fact in valid_facts:
            # evidence_text must be non-empty — every fact needs a source quote
            if not fact.evidence_text.strip():
                raise ModelRetry(
                    f"Fact '{fact.subject} {fact.predicate} {fact.object_value}' "
                    "has empty evidence_text — every fact must reference source text"
                )

            # chapter_id must be non-empty
            if not fact.chapter_id.strip():
                raise ModelRetry(
                    f"Fact '{fact.subject} {fact.predicate} {fact.object_value}' "
                    "has empty chapter_id — every fact must identify its source chapter"
                )

        # Check for duplicates (same subject + predicate + object_value)
        seen: set[tuple[str, str, str]] = set()
        for fact in valid_facts:
            key = (
                fact.subject.strip().lower(),
                fact.predicate.strip().lower(),
                fact.object_value.strip().lower(),
            )
            if key in seen:
                raise ModelRetry(
                    f"Duplicate fact: '{fact.subject} {fact.predicate} {fact.object_value}'"
                )
            seen.add(key)

        return output.model_copy(update={"facts": valid_facts})

    async def run(
        self,
        prompt: str,
        deps: FactExtractorDeps,
        **kwargs: Any,
    ) -> FactExtractorOutput:
        """Execute the fact extraction agent and return structured output.

        Args:
            prompt: The user message / extraction instruction for the agent.
            deps: Dependencies providing chapter texts, KB data, and config.
            **kwargs: Additional arguments passed to pydantic-ai ``run()``.

        Returns:
            Structured fact extraction output with provenance-traced facts.
        """
        return await super().run(prompt, deps, **kwargs)
