"""ReadabilityAgent — NarrareAgent for sentence-level readability analysis.

Uses a pydantic-ai agent to identify problematic sentences and provide
actionable rewrite suggestions that preserve the author's voice.

Deterministic metrics (Flesch, Kincaid, Fog) are computed separately in
``analysis/readability.py`` — this agent handles AI-powered sentence
analysis only.

Usage::

    model = await registry.get_model(config)
    agent = ReadabilityAgent(model=model)
    deps = ReadabilityDeps(text="A long passage...", language="en")
    result = await agent.run(
        prompt="Analyze readability of this text.",
        deps=deps,
    )
    for sentence in result.problematic_sentences:
        print(sentence["issues"])
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext  # noqa: TC002 — needed at runtime by pydantic_ai internals

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.readability_types import ReadabilityAgentOutput


class ReadabilityDeps:
    """Dependencies for ReadabilityAgent.

    Attributes:
        text: The passage / chapter text to analyse.
        language: Language code (``"en"``, ``"de"``, ``"fr"``).
    """

    def __init__(
        self,
        text: str = "",
        language: str = "en",
    ) -> None:
        self.text = text
        self.language = language


class ReadabilityAgent(NarrareAgent[ReadabilityDeps, ReadabilityAgentOutput]):
    """Agent for AI-powered sentence-level readability analysis.

    Takes a text passage, identifies sentences that are hard to read,
    and provides 2-3 rewrite alternatives per problematic sentence
    while preserving the author's voice and style.
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=ReadabilityDeps,
            output_type=[self._process_output, ReadabilityAgentOutput],
            system_prompt=system_prompt,
        )

    async def _process_output(
        self,
        ctx: RunContext[ReadabilityDeps],
        problematic_sentences: list[dict[str, Any]] | None = None,
        overall_assessment: str | None = None,
    ) -> ReadabilityAgentOutput:
        """Output Function — structures the LLM response into ReadabilityAgentOutput.

        During streaming (``ctx.partial_output``) returns a minimal empty result.
        """
        if ctx.partial_output:
            return ReadabilityAgentOutput()

        return ReadabilityAgentOutput(
            problematic_sentences=problematic_sentences or [],
            overall_assessment=overall_assessment or "",
        )

    async def run(
        self,
        prompt: str,
        deps: ReadabilityDeps,
        **kwargs: Any,
    ) -> ReadabilityAgentOutput:
        """Execute the readability agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]
