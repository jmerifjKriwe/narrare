"""CharacterVoiceCheckerAgent — NarrareAgent for qualitative voice checking (WRITE-010).

The qualitative half of ADR-057 Decision 2's hybrid scoring strategy. A single
LLM call checks all supplied characters by interpreting their attributed chapter
dialogue together with (a) the stored *descriptive* voice profile and (b) a
deterministic metric-delta summary (computed by
:mod:`narrare_core.analysis.voice_check_scoring` and supplied to the agent as
runtime context — the agent never recomputes metrics, ADR-021). The agent
produces
:class:`~narrare_core.agents.character_voice_checker_types.CharacterVoiceCheckerOutput`
— a wrapper with a ``characters`` list mirroring the governed ``voice_check``
template's JSON contract.

Decision 5 (scope boundary): this checker is **flag+score only**. It flags
inconsistent lines with profile-grounded reasons and assigns a qualitative
sub-score; it does NOT suggest rewrites (rewrite-on-flagged-line is a separate
feature, WRITE-004). The output type therefore carries no rewrite field.

Prompt loading (RULE-02b): the governed ``voice_check`` template IS the system
prompt. It is resolved Mode 1 by the Layer-3 service via
:class:`~narrare_core.prompts.composer.PromptComposer` and passed to this
agent's constructor as ``system_prompt``. The agent itself contains NO inline
system prompt — it never builds prompts with f-strings (RULE-02). The run prompt
(user channel) carries the attributed dialogue + stored descriptive profile +
metric-delta summary as category-3 runtime content (RULE-02a).

The agent's :attr:`~CharacterVoiceCheckerEntry.qualitative_sub_score` feeds the
Layer 2a blend: :func:`~narrare_core.analysis.voice_check_scoring.blend_scores`
/ :meth:`~narrare_core.analysis.voice_check_scoring.VoiceCheckScorer.score`
combine it with the deterministic metric-delta sub-score into the blended
overall per-character match score. The agent does NOT compute that blend.

Usage::

    model = await registry.get_model(config)
    agent = CharacterVoiceCheckerAgent(
        model=model,
        system_prompt=resolved_template_system,  # from PromptComposer Mode 1
    )
    deps = CharacterVoiceCheckerDeps(
        attributed_dialogue='Elena: \\"I dare say.\\" ...',
        descriptive_profile_summary="Elena: elevated/formal register, ...",
        metric_delta_summary="Elena: avg_sent_len d=0.12, ttr d=0.05, ...",
        character_names=["Elena", "Marc"],
        writing_language="en",
    )
    result = await agent.run(
        prompt=(
            f"Dialogue:\\n{deps.attributed_dialogue}\\n\\n"
            f"Stored profiles:\\n{deps.descriptive_profile_summary}\\n\\n"
            f"Metric deltas:\\n{deps.metric_delta_summary}"
        ),
        deps=deps,
    )
    for entry in result.characters:
        print(entry.character_name, entry.match_judgment, entry.qualitative_sub_score)

See Also
--------
    ADR-057 — Voice-check checking-path contract (Decisions 2 and 5).
    ADR-035 — Agent output validation.
    ADR-054 — Mode-1 PromptComposer mandate.
    narrare_core.analysis.voice_check_scoring — the deterministic blend consumer.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import (
    ModelRetry,
    RunContext,
)

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.character_voice_checker_types import (
    CharacterVoiceCheckerDeps,
    CharacterVoiceCheckerEntry,
    CharacterVoiceCheckerOutput,
)


class CharacterVoiceCheckerAgent(
    NarrareAgent[CharacterVoiceCheckerDeps, CharacterVoiceCheckerOutput]
):
    """Agent for qualitative character-voice consistency checking.

    Takes attributed chapter dialogue + the stored descriptive voice profile(s)
    + a deterministic metric-delta summary (all runtime content) and produces a
    qualitative per-character judgment: a match judgment, a qualitative sub-score
    (0-100), and the specific dialogue lines that read as inconsistent with the
    stored profile, each with a profile-grounded reason.

    The metric-delta is supplied to the model as runtime content — the agent
    interprets it, never recomputes it (ADR-021/ADR-057 Decision 2). It does not
    suggest rewrites (ADR-057 Decision 5).
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=CharacterVoiceCheckerDeps,
            output_type=[self._process_output, CharacterVoiceCheckerOutput],
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[CharacterVoiceCheckerDeps],
        output: CharacterVoiceCheckerOutput,
    ) -> CharacterVoiceCheckerOutput:
        """Validate deterministic invariants for voice-check output.

        ADR-035: enforces output quality at the agent boundary. No side effects
        — deterministic validation only.

        Invariants:
        - At least one character entry must remain after filtering.
        - Entries with an empty ``character_name`` are filtered out (a check
          without a name is useless to the caller).
        - ``qualitative_sub_score`` bounds (0.0-100.0) are enforced by the
          Pydantic Field.
        """
        valid_entries = [e for e in output.characters if e.character_name.strip()]

        if not valid_entries:
            raise ModelRetry(
                "characters list must contain at least one entry with a "
                "non-empty character_name — every voice check needs a name"
            )

        return output.model_copy(update={"characters": valid_entries})

    async def _process_output(
        self,
        ctx: RunContext[CharacterVoiceCheckerDeps],
        characters: list[dict[str, Any]] | None = None,
    ) -> CharacterVoiceCheckerOutput:
        """Output Function — structures the LLM response into the output type.

        During streaming (``ctx.partial_output``) returns a minimal empty result.
        """
        if ctx.partial_output:
            return CharacterVoiceCheckerOutput()

        return CharacterVoiceCheckerOutput(
            characters=[CharacterVoiceCheckerEntry(**c) for c in (characters or [])],
        )

    async def run(
        self,
        prompt: str,
        deps: CharacterVoiceCheckerDeps,
        **kwargs: Any,
    ) -> CharacterVoiceCheckerOutput:
        """Execute the voice-checker agent and return structured output."""
        return await super().run(prompt, deps, **kwargs)
