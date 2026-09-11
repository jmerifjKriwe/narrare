"""CharacterVoiceAgent — NarrareAgent for qualitative voice profiling (ANAL-008).

The qualitative half of ADR-055 Decision 2's hybrid metrics strategy. A single
LLM call profiles all supplied characters by interpreting their attributed
dialogue together with the deterministic
:class:`~narrare_core.kb.schemas.character.VoiceMetrics` (computed by
:class:`~narrare_core.analysis.voice_metrics.VoiceMetricsAnalyzer`). The agent
produces :class:`~narrare_core.agents.character_voice_types.CharacterVoiceOutput`
— a wrapper with a ``characters`` list mirroring the governed ``character_voice``
template's JSON contract.

Prompt loading (RULE-02b): the governed ``character_voice`` template IS the
system prompt. It is resolved Mode 1 by the Layer-3 service via
:class:`~narrare_core.prompts.composer.PromptComposer` and passed to this
agent's constructor as ``system_prompt``. The agent itself contains NO inline
system prompt — it never builds prompts with f-strings (RULE-02). The run
prompt (user channel) carries the attributed dialogue + per-character metrics
as category-3 runtime content (RULE-02a).

Usage::

    model = await registry.get_model(config)
    agent = CharacterVoiceAgent(
        model=model,
        system_prompt=resolved_template_system,  # from PromptComposer Mode 1
    )
    deps = CharacterVoiceDeps(
        attributed_dialogue="Elena: \\"Hello.\\" ...",
        voice_metrics_summary="Elena: avg_sent_len=5.2, ttr=0.71, ...",
        character_names=["Elena", "Marc"],
        writing_language="en",
    )
    result = await agent.run(
        prompt=f"Dialogue:\\n{deps.attributed_dialogue}\\n\\nMetrics:\\n{deps.voice_metrics_summary}",
        deps=deps,
    )
    for entry in result.characters:
        print(entry.character_name, entry.formality, entry.emotional_range)

See Also
--------
ADR-055 — Character voice storage contract (Decisions 1, 2, 3).
ADR-035 — Agent output validation.
ADR-054 — Mode-1 PromptComposer mandate.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import (
    ModelRetry,
    RunContext,
)

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.character_voice_types import (
    CharacterVoiceDeps,
    CharacterVoiceOutput,
)


class CharacterVoiceAgent(NarrareAgent[CharacterVoiceDeps, CharacterVoiceOutput]):
    """Agent for qualitative character-voice profiling.

    Takes attributed dialogue text + per-character deterministic voice metrics
    and produces a qualitative voice profile per character (formality register,
    vocabulary level, sentence profile, emotional range, cultural/regional
    markers, curated example quotes, and per-run distinctiveness notes).

    The deterministic metrics are supplied to the model as runtime content —
    the agent interprets them, never recomputes them (ADR-055 Decision 2).
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=CharacterVoiceDeps,
            output_type=CharacterVoiceOutput,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[CharacterVoiceDeps],
        output: CharacterVoiceOutput,
    ) -> CharacterVoiceOutput:
        """Validate deterministic invariants for character-voice output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - At least one character entry must remain after filtering.
        - Entries with an empty ``character_name`` are filtered out
          (a profile without a name is useless to the caller).
        - ``formality`` bounds are enforced by the Pydantic Field (0.0-1.0).
        """
        valid_entries = [e for e in output.characters if e.character_name.strip()]

        if not valid_entries:
            raise ModelRetry(
                "characters list must contain at least one entry with a "
                "non-empty character_name — every voice profile needs a name"
            )

        return output.model_copy(update={"characters": valid_entries})

    async def run(
        self,
        prompt: str,
        deps: CharacterVoiceDeps,
        **kwargs: Any,
    ) -> CharacterVoiceOutput:
        """Execute the character-voice agent and return structured output."""
        return await super().run(prompt, deps, **kwargs)
