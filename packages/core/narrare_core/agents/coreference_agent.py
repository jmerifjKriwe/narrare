"""CoreferenceAgent — NarrareAgent for coreference resolution analysis.

Resolves pronoun references to their referents (character names), flags
ambiguous pronouns, tracks character mentions, and scores overall
referential clarity of a passage.

LLM-based (ANAL-005): the model performs full coreference resolution and
returns structured output. There is no deterministic spaCy fallback — the
analysis relies entirely on the LLM's language understanding.

Usage::

    model = await registry.get_model(config)
    agent = CoreferenceAgent(model=model)
    deps = CoreferenceDeps(
        text="Alice looked at Bob. She smiled...",
        writing_language="en",
    )
    result = await agent.run(
        prompt="Resolve coreference in this text.",
        deps=deps,
    )
    for resolution in result.resolutions:
        print(resolution.pronoun, "->", resolution.referent)
    print("Clarity:", result.clarity_score)
"""

from __future__ import annotations

from typing import Any, cast

from pydantic_ai import (
    ModelRetry,
    RunContext,
)

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.coreference_types import (
    CharacterMention,
    CoreferenceDeps,
    CoreferenceOutput,
    PronounResolution,
)


class CoreferenceAgent(NarrareAgent[CoreferenceDeps, CoreferenceOutput]):
    """Agent for coreference resolution and clarity analysis.

    Takes a text passage and identifies all pronouns, mapping each to its
    referent (character name). Ambiguous pronouns (multiple plausible
    referents) are flagged. The agent also tracks which characters appear
    in the passage and assigns an overall referential-clarity score.
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=CoreferenceDeps,
            output_type=[self._process_output, CoreferenceOutput],
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[CoreferenceDeps],
        output: CoreferenceOutput,
    ) -> CoreferenceOutput:
        """Validate deterministic invariants for coreference output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - summary must be non-empty
        - confidence values must be within 0.0-1.0 (enforced by Field)
        - Filter out resolutions with an empty pronoun token
        """
        # summary must be non-empty — every analysis needs an assessment
        if not output.summary.strip():
            raise ModelRetry(
                "summary must be non-empty — every coreference analysis needs an assessment"
            )

        # Filter out resolutions with an empty pronoun token
        valid_resolutions = [r for r in output.resolutions if r.pronoun.strip()]

        return output.model_copy(
            update={
                "resolutions": valid_resolutions,
            }
        )

    async def _process_output(
        self,
        ctx: RunContext[CoreferenceDeps],
        resolutions: list[dict[str, Any]] | None = None,
        character_mentions: list[dict[str, Any]] | None = None,
        clarity_score: float | None = None,
        summary: str | None = None,
    ) -> CoreferenceOutput:
        """Output Function — structures the LLM response into CoreferenceOutput.

        During streaming (``ctx.partial_output``) returns a minimal empty result.
        """
        if ctx.partial_output:
            return CoreferenceOutput()

        return CoreferenceOutput(
            resolutions=[PronounResolution(**r) for r in (resolutions or [])],
            character_mentions=[CharacterMention(**m) for m in (character_mentions or [])],
            clarity_score=clarity_score if clarity_score is not None else 0.0,
            summary=summary or "",
        )

    async def run(
        self,
        prompt: str,
        deps: CoreferenceDeps,
        **kwargs: Any,
    ) -> CoreferenceOutput:
        """Execute the coreference agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return cast("CoreferenceOutput", result.output)
