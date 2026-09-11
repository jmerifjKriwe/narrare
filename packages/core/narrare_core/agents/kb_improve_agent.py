"""KBImproveAgent — KB entry improvement analysis agent.

Analyzes an existing KB entry and returns structured improvement
suggestions with confidence scores. Does NOT generate content —
it identifies gaps, weaknesses, and opportunities.

Usage:
    model = await registry.get_model(config)
    agent = KBImproveAgent(model=model, kb_agent=kb_agent)
    deps = KBImproveDeps(
        language="en",
        entity_type="character",
        template_structure={...},
        entry_content={"name": "Anna", "age": 28},
        world_context="...",
    )
    result = await agent.run(prompt="Analyze this entry", deps=deps)
    # result.suggestions, result.overall_assessment, result.completeness_score
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import (
    ModelRetry,
    RunContext,
)
from pydantic_ai.capabilities import ToolSearch, Toolset

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.kb_improve_types import (
    KBImproveDeps,
    KBImproveOutput,
)

if TYPE_CHECKING:
    from narrare_core.agents.kb_agent import KBAgent


class KBImproveAgent(NarrareAgent[KBImproveDeps, KBImproveOutput]):
    """Agent that analyzes KB entries and returns improvement suggestions.

    Composes with KBAgent for world context queries via Toolset capability.
    When no KBAgent is provided, operates in template-comparison-only mode
    (less thorough suggestions).
    """

    def __init__(
        self,
        model: Any,
        kb_agent: KBAgent | None = None,
        system_prompt: str | None = None,
    ) -> None:
        # Build capabilities: ToolSearch + KBAgent tools when available
        capabilities: list[Any] = []
        if kb_agent is not None:
            capabilities.append(ToolSearch(strategy="keywords"))
            capabilities.append(Toolset(kb_agent.get_toolset()))

        super().__init__(
            model=model,
            deps_type=KBImproveDeps,
            output_type=KBImproveOutput,
            capabilities=capabilities,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[KBImproveDeps],
        output: KBImproveOutput,
    ) -> KBImproveOutput:
        """Validate deterministic invariants for KB improve output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - target field must be non-empty for each suggestion
        - description must be non-empty for each suggestion
        - Filter suggestions with empty target or description
        - completeness_score clamped to [0.0, 1.0]
        """
        # Filter suggestions with empty target or description
        valid_suggestions = [
            s for s in output.suggestions if s.target.strip() and s.description.strip()
        ]

        for s in valid_suggestions:
            # target must be non-empty
            if not s.target.strip():
                raise ModelRetry(
                    "Suggestion has an empty target — every suggestion needs a target field"
                )
            # description must be non-empty
            if not s.description.strip():
                raise ModelRetry(
                    f"Suggestion for '{s.target}' has an empty description — "
                    "every suggestion needs a description"
                )

        # completeness_score clamped to [0.0, 1.0]
        clamped_score = min(max(output.completeness_score, 0.0), 1.0)

        return output.model_copy(
            update={
                "suggestions": valid_suggestions,
                "completeness_score": clamped_score,
            }
        )

    async def run(
        self,
        prompt: str,
        deps: KBImproveDeps,
        **kwargs: Any,
    ) -> KBImproveOutput:
        """Execute the improve agent and return structured output."""
        return await super().run(prompt, deps, **kwargs)
