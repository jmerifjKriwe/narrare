"""ConsistencyAgent — Detects contradictions across chapters and KB data.

Cross-chapter and cross-entity consistency checking for:
- Character consistency (behavior, voice, knowledge, abilities)
- Timeline consistency (event sequencing, durations, ages)
- World consistency (locations, systems, factions)
- Plot consistency (cause/effect, motivations, loose ends)

Follows the same pattern as ExtractionAgent — NarrareAgent subclass with
Output Function for post-processing and optional KBAgent composition.

Usage:
    model = await registry.get_model(config)
    agent = ConsistencyAgent(model=model, kb_agent=kb_agent)
    deps = ConsistencyDeps(
        language="en",
        novel_id="novel-123",
        chapter_texts={"ch1": "Chapter 1 content...", "ch2": "Chapter 2 content..."},
        kb_entity_summaries=[
            {"entity_type": "character", "name": "Anna", "traits": ["brave", "impulsive"]},
        ],
        check_types=[ConsistencyCheckType.CHARACTER],
    )
    result = await agent.run(prompt="Check for contradictions.", deps=deps)
    for issue in result.issues:
        print(f"[{issue.severity}] {issue.description}")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import (
    ModelRetry,
    RunContext,
)
from pydantic_ai.capabilities import ToolSearch, Toolset

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.consistency_types import (
    ConsistencyDeps,
    ConsistencyOutput,
    ConsistencySeverity,
)

if TYPE_CHECKING:
    from narrare_core.agents.kb_agent import KBAgent


class ConsistencyAgent(NarrareAgent[ConsistencyDeps, ConsistencyOutput]):
    """Agent for cross-entity and cross-chapter consistency checking.

    Compares facts extracted from chapter prose against KB entity data
    and other chapters. Identifies contradictions with severity ratings
    and location references.

    Composes with KBAgent for KB entity lookup when available.
    When no KBAgent is provided, relies on ``deps.kb_entity_summaries``
    for KB context.
    """

    def __init__(
        self,
        model: Any,
        kb_agent: KBAgent | None = None,
        system_prompt: str | None = None,
    ) -> None:
        """Initialize ConsistencyAgent.

        Args:
            model: LLM model from ModelRegistry.
            kb_agent: Optional KBAgent for KB entity lookup via ToolSearch/Toolset.
            system_prompt: Optional system prompt. Built by service layer when
                using PromptComposer. NarrareMeta Capability is always active.
        """
        capabilities: list[Any] = []
        if kb_agent is not None:
            capabilities.append(ToolSearch(strategy="keywords"))
            capabilities.append(Toolset(kb_agent.get_toolset()))

        super().__init__(
            model=model,
            deps_type=ConsistencyDeps,
            output_type=ConsistencyOutput,
            capabilities=capabilities,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[ConsistencyDeps],
        output: ConsistencyOutput,
    ) -> ConsistencyOutput:
        """Validate deterministic invariants for consistency output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - Each issue must have a non-empty description
        - conflicting_facts must have >= 2 entries (contradiction needs 2+ facts)
        - ERROR-severity issues must have a suggestion
        - Filter out issues with empty descriptions
        """
        # Filter out issues with empty descriptions
        valid_issues = [issue for issue in output.issues if issue.description.strip()]

        for issue in valid_issues:
            # conflicting_facts must have at least 2 entries
            if len(issue.conflicting_facts) < 2:
                raise ModelRetry(
                    f"Consistency issue '{issue.description[:50]}' must have at least "
                    f"2 conflicting_facts, got {len(issue.conflicting_facts)}"
                )

            # ERROR severity issues must have a suggestion
            if issue.severity == ConsistencySeverity.ERROR and (
                not issue.suggestion or not issue.suggestion.strip()
            ):
                raise ModelRetry(
                    f"ERROR-severity issue '{issue.description[:50]}' must have "
                    "a non-empty suggestion"
                )

        return output.model_copy(update={"issues": valid_issues})

    async def run(
        self,
        prompt: str,
        deps: ConsistencyDeps,
        **kwargs: Any,
    ) -> ConsistencyOutput:
        """Execute the consistency agent and return structured output.

        Args:
            prompt: The user message / analysis request for the agent.
            deps: Dependencies providing chapter texts, KB data, and config.
            **kwargs: Additional arguments passed to pydantic-ai ``run()``.

        Returns:
            Structured consistency output with issues and overall assessment.
        """
        return await super().run(prompt, deps, **kwargs)
