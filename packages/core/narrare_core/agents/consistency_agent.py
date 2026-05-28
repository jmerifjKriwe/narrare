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

from pydantic_ai import RunContext  # noqa: TC002 — needed at runtime by pydantic_ai internals
from pydantic_ai.capabilities import ToolSearch, Toolset

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.consistency_types import ConsistencyDeps, ConsistencyOutput

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
                using PromptComposer. Passed directly when using ``with_meta()``.
        """
        capabilities: list[Any] = []
        if kb_agent is not None:
            capabilities.append(ToolSearch(strategy="keywords"))
            capabilities.append(Toolset(kb_agent.get_toolset()))

        super().__init__(
            model=model,
            deps_type=ConsistencyDeps,
            output_type=[self._process_output, ConsistencyOutput],
            capabilities=capabilities,
            system_prompt=system_prompt,
        )

    async def _process_output(
        self,
        ctx: RunContext[ConsistencyDeps],
        issues: list[dict[str, Any]] | None = None,
        overall_assessment: str = "",
        checked_types: list[str] | None = None,
    ) -> ConsistencyOutput:
        """Output Function — structures the LLM response into ConsistencyOutput.

        During streaming (ctx.partial_output), returns a minimal empty result.
        Consistency checking is non-streaming by nature, but the output function
        pattern is required for type-safe structured output with pydantic-ai.
        """
        if ctx.partial_output:
            return ConsistencyOutput()

        from narrare_core.agents.consistency_types import ConsistencyCheckType, ConsistencyIssue

        items: list[ConsistencyIssue] = []
        for issue in issues or []:
            items.append(ConsistencyIssue.model_validate(issue))

        return ConsistencyOutput(
            issues=items,
            overall_assessment=overall_assessment,
            checked_types=[ConsistencyCheckType(t) for t in (checked_types or [])],
        )

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
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]
