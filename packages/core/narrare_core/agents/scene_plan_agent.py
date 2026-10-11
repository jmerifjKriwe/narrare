"""ScenePlanAgent — scene planning for chapters (draft) and scenes (refine).

Usage:
    model = await registry.get_model(config)
    agent = ScenePlanAgent(model=model, output_type=SceneDraftOutput)
    deps = ScenePlanDeps(language="en", genre="Fantasy", project_title="The Last Kingdom")
    result = await agent.run(
        prompt="<chapter_context>Ch 4 summary…</chapter_context><instruction>…</instruction>",
        deps=deps,
    )
    for proposal in result.scenes:  # SceneDraftOutput
        print(proposal.title, proposal.purpose)

Refine runs construct the agent with ``output_type=SceneRefineOutput``
instead — one agent class, two governed output contracts (PLAN-001 §6.1).
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import (
    ModelRetry,
    RunContext,
)

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.scene_plan_types import (
    SceneDraftOutput,
    ScenePlanDeps,
    SceneProposal,
    SceneRefineOutput,
)

__all__ = ["ScenePlanAgent", "ScenePlanDeps"]


class ScenePlanAgent(NarrareAgent[ScenePlanDeps, SceneDraftOutput | SceneRefineOutput]):
    """Scene-planning agent — chapter draft (N scenes) or single-scene refine.

    Task framing comes from the governed PLAN modes (``scene_plan_draft`` /
    ``scene_plan_refine``) via ``PromptComposer``; the run prompt carries the
    XML-wrapped chapter/scene runtime data (category-3, RULE-02a).
    """

    def __init__(
        self,
        model: Any,
        output_type: type[SceneDraftOutput] | type[SceneRefineOutput],
        system_prompt: str | None = None,
    ) -> None:
        super().__init__(
            model=model,
            deps_type=ScenePlanDeps,
            output_type=output_type,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[ScenePlanDeps],
        output: SceneDraftOutput | SceneRefineOutput,
    ) -> SceneDraftOutput | SceneRefineOutput:
        """Validate deterministic invariants for scene-plan output.

        ADR-035: output quality is enforced at the agent boundary.
        No side effects — deterministic validation only.

        Invariant: every proposal needs substance — title and purpose
        must not both be empty (whitespace counts as empty).
        """
        if isinstance(output, SceneDraftOutput):
            for proposal in output.scenes:
                _require_substance(proposal)
        else:
            _require_substance(output.scene)
        return output


def _require_substance(proposal: SceneProposal) -> None:
    """Reject a proposal whose title and purpose are both empty."""
    if not proposal.title.strip() and not proposal.purpose.strip():
        raise ModelRetry(
            "Every scene proposal needs a non-empty title or purpose — "
            "an empty scene cannot be planned"
        )
