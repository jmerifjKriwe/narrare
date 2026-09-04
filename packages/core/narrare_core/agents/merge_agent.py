"""KBMergeAgent — NarrareAgent for Knowledge Base merge analysis.

Usage:
    model = await registry.get_model(config)
    agent = KBMergeAgent(model=model)
    deps = KBMergeDeps(
        entity_type="character",
        genre="Fantasy",
        language="en",
    )
    result = await agent.run(
        prompt="Evaluate candidate pairs for merge.",
        deps=deps,
    )
    print(result.merge_decisions)
    print(result.overall_notes)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import (
    ModelRetry,
    RunContext,
)

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.merge_types import MergeOutput

if TYPE_CHECKING:
    from narrare_core.writing.context_assembler import WritingContextAssembler


class KBMergeDeps:
    """Dependencies for KBMergeAgent.

    Attributes:
        entity_type: Type of entities being merged (e.g. "character", "location").
        genre: Story genre (e.g. "Fantasy", "Sci-Fi").
        language: Output language code.
        context_assembler: Optional context provider for additional context.
    """

    def __init__(
        self,
        entity_type: str = "",
        genre: str = "",
        language: str = "en",
        context_assembler: WritingContextAssembler | None = None,
    ) -> None:
        self.entity_type = entity_type
        self.genre = genre
        self.language = language
        self.context_assembler = context_assembler


class KBMergeAgent(NarrareAgent[KBMergeDeps, MergeOutput]):
    """Agent for Knowledge Base merge analysis.

    Evaluates candidate duplicate pairs and recommends merge strategies,
    deciding whether two entities should be merged, kept distinct,
    or flagged as uncertain for human review.
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=KBMergeDeps,
            output_type=MergeOutput,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[KBMergeDeps],
        output: MergeOutput,
    ) -> MergeOutput:
        """Validate deterministic invariants for merge output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - decision should be one of "merge", "distinct", "uncertain"
        - pair_id must be non-empty for each decision
        - When decision is "merge", merge_strategy must be present
        - No duplicate pair_ids
        """
        valid_decisions = {"merge", "distinct", "uncertain"}

        # No duplicate pair_ids
        seen_pair_ids: set[str] = set()
        for idx, d in enumerate(output.merge_decisions):
            if d.pair_id in seen_pair_ids:
                raise ModelRetry(
                    f"Duplicate pair_id '{d.pair_id}' at index {idx} — "
                    "each pair must be decided exactly once"
                )
            seen_pair_ids.add(d.pair_id)

        for d in output.merge_decisions:
            # pair_id must be non-empty
            if not d.pair_id.strip():
                raise ModelRetry("Each merge decision must have a non-empty pair_id")

            # decision must be one of the valid values
            if d.decision not in valid_decisions:
                raise ModelRetry(f"Decision must be one of {valid_decisions}, got '{d.decision}'")

            # When decision is "merge", merge_strategy must be present
            if d.decision == "merge" and d.merge_strategy is None:
                raise ModelRetry(
                    f"Decision 'merge' for pair '{d.pair_id}' must include a merge_strategy"
                )

        return output

    async def run(
        self,
        prompt: str,
        deps: KBMergeDeps,
        **kwargs: Any,
    ) -> MergeOutput:
        """Execute the KB merge agent and return structured output."""
        return await super().run(prompt, deps, **kwargs)
