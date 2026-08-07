"""WorldbuildingAgent — project-level worldbuilding analysis.

Two-phase analysis:
  Phase 1: Gap detection + connection suggestions (entity summaries)
  Phase 2: Consistency checking (entity pair deep-dive)

Composes with KBAgent for entity lookup tools during analysis.

Usage:
    model = await registry.get_model(config)
    agent = WorldbuildingAgent(model=model, kb_agent=kb_agent)
    deps = WorldbuildingDeps(
        language="en",
        entity_summaries=[Phase1EntitySummary(...)],
        template_structures={...},
        existing_relationships=[...],
        world_context="...",
    )
    result = await agent.run_phase1(prompt="Analyze worldbuilding", deps=deps)
    # result.gaps, result.connection_suggestions, result.worldbuilding_score

    # Then optionally Phase 2:
    phase2_result = await agent.run_phase2(
        prompt="Check consistency for these pairs",
        deps=WorldbuildingDeps(candidate_pairs=[("ent-1", "ent-2")]),
        model=model,  # Can use different model for Phase 2
    )
    # phase2_result.issues, phase2_result.assessment
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

# RunContext must be at runtime — pydantic-ai calls get_type_hints()
# on output functions passed via output_type= (TC002 suppressed)
from pydantic_ai import RunContext  # noqa: TC002
from pydantic_ai.capabilities import ToolSearch, Toolset

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.worldbuilding_types import (
    Phase1ConnectionOutput,
    Phase1GapOutput,
    Phase2ConsistencyOutput,
    WorldbuildingDeps,
    WorldbuildingPhase1Output,
    WorldbuildingPhase2Output,
)
from narrare_core.agents.worldbuilding_validators import (
    validate_worldbuilding_phase1,
    validate_worldbuilding_phase2,
)

if TYPE_CHECKING:
    from narrare_core.agents.kb_agent import KBAgent


class WorldbuildingAgent(NarrareAgent[WorldbuildingDeps, WorldbuildingPhase1Output]):
    """Agent that analyzes project-level worldbuilding health.

    Phase 1: Receives entity summaries, detects gaps and suggests connections.
    Phase 2: Receives entity pairs + full details, checks consistency.

    Composes with KBAgent for optional entity lookup during analysis.
    """

    def __init__(
        self,
        model: Any,
        kb_agent: KBAgent | None = None,
        system_prompt: str | None = None,
    ) -> None:
        """Initialize WorldbuildingAgent.

        Args:
            model: LLM model from ModelRegistry.
            kb_agent: Optional KBAgent for entity lookup tools.
            system_prompt: Optional override for the system prompt.
        """
        capabilities: list[Any] = []
        if kb_agent is not None:
            capabilities.append(ToolSearch(strategy="keywords"))
            capabilities.append(Toolset(kb_agent.get_toolset()))

        super().__init__(
            model=model,
            deps_type=WorldbuildingDeps,
            output_type=[self._process_phase1, WorldbuildingPhase1Output],
            capabilities=capabilities,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(validate_worldbuilding_phase1)

    async def _process_phase1(
        self,
        ctx: RunContext[WorldbuildingDeps],
        gaps: list[dict[str, Any]] | None = None,
        connection_suggestions: list[dict[str, Any]] | None = None,
        assessment: str = "",
        worldbuilding_score: float = 0.0,
        candidate_pairs: list[list[str]] | None = None,
    ) -> WorldbuildingPhase1Output:
        """Output Function for Phase 1 — structures LLM response.

        This is a pydantic-ai output function (tool-like) that transforms
        the raw LLM response dicts into validated Pydantic models.

        During streaming (ctx.partial_output), returns minimal result.
        """
        if ctx.partial_output:
            return WorldbuildingPhase1Output(
                gaps=[],
                connection_suggestions=[],
                assessment="",
                worldbuilding_score=0.0,
                candidate_pairs_for_consistency=[],
            )

        parsed_gaps = [Phase1GapOutput(**g) for g in (gaps or [])]
        parsed_connections = [Phase1ConnectionOutput(**c) for c in (connection_suggestions or [])]
        parsed_pairs = [(p[0], p[1]) for p in (candidate_pairs or []) if len(p) == 2]

        return WorldbuildingPhase1Output(
            gaps=parsed_gaps,
            connection_suggestions=parsed_connections,
            assessment=assessment,
            worldbuilding_score=min(max(worldbuilding_score, 0.0), 1.0),
            candidate_pairs_for_consistency=parsed_pairs,
        )

    async def run_phase1(
        self,
        prompt: str,
        deps: WorldbuildingDeps,
        **kwargs: Any,
    ) -> WorldbuildingPhase1Output:
        """Execute Phase 1 analysis (gaps + connections)."""
        return await super().run(prompt, deps, **kwargs)

    async def run_phase2(
        self,
        prompt: str,
        deps: WorldbuildingDeps,
        model: Any,  # Phase 2 can use a different model
        system_prompt: str | None = None,
    ) -> WorldbuildingPhase2Output:
        """Execute Phase 2 consistency checking with separate agent instance.

        Phase 2 uses its own agent instance because it has different
        output type and potentially different model/system prompt.

        Args:
            prompt: The user prompt for consistency checking.
            deps: WorldbuildingDeps with candidate_pairs and entity_details.
            model: LLM model from ModelRegistry (can differ from Phase 1).
            system_prompt: Optional override for the system prompt.

        Returns:
            WorldbuildingPhase2Output with consistency issues and assessment.
        """
        phase2_agent = NarrareAgent[WorldbuildingDeps, WorldbuildingPhase2Output](
            model=model,
            deps_type=WorldbuildingDeps,
            output_type=[self._process_phase2, WorldbuildingPhase2Output],
            system_prompt=system_prompt,
        )
        phase2_agent._agent.output_validator(validate_worldbuilding_phase2)
        result = await phase2_agent.run(prompt, deps=deps)
        return result

    async def _process_phase2(
        self,
        ctx: RunContext[WorldbuildingDeps],
        issues: list[dict[str, Any]] | None = None,
        assessment: str = "",
    ) -> WorldbuildingPhase2Output:
        """Output Function for Phase 2 consistency checking.

        During streaming (ctx.partial_output), returns minimal result.
        """
        if ctx.partial_output:
            return WorldbuildingPhase2Output(issues=[], assessment="")

        parsed = [Phase2ConsistencyOutput(**i) for i in (issues or [])]
        return WorldbuildingPhase2Output(issues=parsed, assessment=assessment)

    async def run(
        self,
        prompt: str,
        deps: WorldbuildingDeps,
        **kwargs: Any,
    ) -> WorldbuildingPhase1Output:
        """Default run for Phase 1 (backwards compatibility).

        Prefer run_phase1() for explicit clarity.
        """
        return await self.run_phase1(prompt, deps, **kwargs)
