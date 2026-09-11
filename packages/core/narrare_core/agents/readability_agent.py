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

from pydantic_ai import (
    ModelRetry,
    RunContext,
)

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
            output_type=ReadabilityAgentOutput,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[ReadabilityDeps],
        output: ReadabilityAgentOutput,
    ) -> ReadabilityAgentOutput:
        """Validate deterministic invariants for readability output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - overall_assessment non-empty
        - Filter problematic_sentences with empty content
        """
        # overall_assessment must be non-empty
        if not output.overall_assessment.strip():
            raise ModelRetry(
                "overall_assessment must be non-empty — "
                "every readability analysis needs an assessment"
            )

        # Filter problematic_sentences with empty content
        valid_sentences = [
            s
            for s in output.problematic_sentences
            if s.get("content", s.get("sentence", "")).strip()
        ]

        return output.model_copy(
            update={
                "problematic_sentences": valid_sentences,
            }
        )

    async def run(
        self,
        prompt: str,
        deps: ReadabilityDeps,
        **kwargs: Any,
    ) -> ReadabilityAgentOutput:
        """Execute the readability agent and return structured output."""
        return await super().run(prompt, deps, **kwargs)
