"""POVDetectionAgent — NarrareAgent for POV analysis.

Detects POV character per scene, identifies head-hopping, knowledge
leakage, emotional leakage, and physical impossibility violations.

Usage::

    model = await registry.get_model(config)
    agent = POVDetectionAgent(model=model)
    deps = POVDeps(
        text="Alice felt a chill run down her spine...",
        language="en",
        known_characters=["Alice", "Bob"],
        pov_type_hint="third_limited",
    )
    result = await agent.run(
        prompt="Analyze POV in this text.",
        deps=deps,
    )
    for scene in result.scenes:
        print(scene.pov_character, scene.confidence)
    for issue in result.issues:
        print(issue.type, issue.severity, issue.text)
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext  # noqa: TC002 — needed at runtime by pydantic_ai internals

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.pov_types import (
    POVDetectedIssue,
    POVDetectedScene,
    POVDetectionOutput,
)


class POVDeps:
    """Dependencies for POVDetectionAgent.

    Attributes:
        text: The passage / chapter text to analyse.
        language: Language code (``"en"``, ``"de"``, ``"fr"``).
        known_characters: List of known character names for POV assignment.
        pov_type_hint: Expected POV type (``"third_limited"``,
            ``"first_person"``, ``"omniscient"``).
    """

    def __init__(
        self,
        text: str = "",
        language: str = "en",
        known_characters: list[str] | None = None,
        pov_type_hint: str | None = None,
    ) -> None:
        self.text = text
        self.language = language
        self.known_characters = known_characters or []
        self.pov_type_hint = pov_type_hint


class POVDetectionAgent(NarrareAgent[POVDeps, POVDetectionOutput]):
    """Agent for POV character detection and violation analysis.

    Takes a text passage (optionally with known characters and a POV
    type hint), identifies the POV character per scene, and flags
    violations such as head-hopping, knowledge leakage, emotional
    leakage, and physical impossibility.
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=POVDeps,
            output_type=[self._process_output, POVDetectionOutput],
            system_prompt=system_prompt,
        )

    async def _process_output(
        self,
        ctx: RunContext[POVDeps],
        scenes: list[dict[str, Any]] | None = None,
        issues: list[dict[str, Any]] | None = None,
        pov_distribution: dict[str, float] | None = None,
        switch_count: int | None = None,
        analysis_type: str | None = None,
        overall_assessment: str | None = None,
    ) -> POVDetectionOutput:
        """Output Function — structures the LLM response into POVDetectionOutput.

        During streaming (``ctx.partial_output``) returns a minimal empty result.
        """
        if ctx.partial_output:
            return POVDetectionOutput()

        return POVDetectionOutput(
            scenes=[POVDetectedScene(**s) for s in (scenes or [])],
            issues=[POVDetectedIssue(**i) for i in (issues or [])],
            pov_distribution=pov_distribution or {},
            switch_count=switch_count or 0,
            analysis_type=analysis_type or "",
            overall_assessment=overall_assessment or "",
        )

    async def run(
        self,
        prompt: str,
        deps: POVDeps,
        **kwargs: Any,
    ) -> POVDetectionOutput:
        """Execute the POV detection agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]
