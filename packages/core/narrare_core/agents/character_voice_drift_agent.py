"""CharacterVoiceDriftAgent — NarrareAgent for longitudinal drift classification (ANAL-009).

The qualitative half of ADR-073 Decision 3's hybrid drift strategy. A single
LLM call **per character** classifies the longitudinal voice drift across
chapters by interpreting (a) the stored *descriptive* voice profile, (b) a
precomputed per-chapter match trend (signal i), and (c) detected adjacent-
chapter jump points (signal iii) — all supplied as runtime context. The agent
produces :class:`~narrare_core.agents.character_voice_drift_types.VoiceDriftResult`
— a flat structured object mirroring the governed ``voice_drift`` template's
JSON contract.

Measurement is already done by
:mod:`narrare_core.analysis.voice_drift_scoring` (deterministic, ADR-021); the
agent ONLY interprets the trend qualitatively (ADR-021 hybrid tier — mirrors
ANAL-003/008/057). It never recomputes metrics, distances, or bands.

Decision 5 scope boundary: this agent is **read-only classification only**. It
does NOT suggest rewrites (WRITE-004) and does NOT build/update a voice
profile (ANAL-008). The output type therefore carries no rewrite or profile
field.

Prompt loading (RULE-02b): the governed ``voice_drift`` template IS the system
prompt. It is resolved Mode 1 by the Layer-3 service via
:class:`~narrare_core.prompts.composer.PromptComposer` and passed to this
agent's constructor as ``system_prompt``. The agent itself contains NO inline
system prompt — it never builds prompts with f-strings (RULE-02). The run
prompt (user channel) carries the descriptive profile + precomputed trend +
jumps + chapter metadata as category-3 runtime content (RULE-02a).

RULE-13 (ADR-065): ``run()`` returns the structured
:class:`VoiceDriftResult`; streaming is inherited from
:class:`~narrare_core.agents.base.NarrareAgent` (``run_stream()``) — mirrors
the sibling :class:`CharacterVoiceAgent` / :class:`CharacterVoiceCheckerAgent`.

Usage::

    model = await registry.get_model(config)
    agent = CharacterVoiceDriftAgent(
        model=model,
        system_prompt=resolved_template_system,  # from PromptComposer Mode 1
    )
    deps = CharacterVoiceDriftDeps(
        character_name="Elena",
        descriptive_profile="Elena: elevated/formal register, ...",
        trend=trend_points,        # from trend_against_profile()
        jumps=jump_points,         # from detect_adjacent_jumps()
        chapter_meta=[ChapterMeta(chapter_id="ch-1", title="The Arrival")],
        writing_language="en",
    )
    result = await agent.run(
        prompt=(
            f"Character: {deps.character_name}\\n\\n"
            f"Stored profile:\\n{deps.descriptive_profile}\\n\\n"
            f"Trend:\\n{format_trend(deps.trend)}\\n\\n"
            f"Jumps:\\n{format_jumps(deps.jumps)}\\n\\n"
            f"Chapters:\\n{format_meta(deps.chapter_meta)}"
        ),
        deps=deps,
    )
    print(result.drift_type, result.confidence, result.suggested_attention)

See Also
--------
    ADR-073 — Character Voice Drift (Decision 3 agent role, Decision 5 scope).
    ADR-035 — Agent output validation.
    ADR-054 — Mode-1 PromptComposer mandate.
    narrare_core.analysis.voice_drift_scoring — the precomputed trend + jumps.
"""

from __future__ import annotations

from typing import Any

# RunContext is intentionally a RUNTIME import (not TYPE_CHECKING): pydantic-ai
# introspects output-validator signatures at agent-construction time, so the
# annotation ``ctx: RunContext[...]`` MUST resolve at runtime.
# Mirrors CharacterVoiceCheckerAgent. noqa: TC002.
from pydantic_ai import RunContext  # noqa: TC002

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.character_voice_drift_types import (
    CharacterVoiceDriftDeps,
    VoiceDriftResult,
)


class CharacterVoiceDriftAgent(NarrareAgent[CharacterVoiceDriftDeps, VoiceDriftResult]):
    """Agent for longitudinal character-voice drift classification.

    Takes the stored descriptive voice profile + a precomputed per-chapter
    match trend + detected adjacent-chapter jump points + chapter metadata
    (all runtime content) and produces a single qualitative classification:
    a ``drift_type`` (evolution / context / inconsistency), a confidence, the
    longitudinal reasons that drove the classification, sparse per-chapter
    notes, and the chapter ids most worth the author's review.

    The trend + jumps are supplied to the model as runtime content — the agent
    interprets them, never recomputes them (ADR-021/ADR-073 Decision 2). It
    does not suggest rewrites and does not build a profile (ADR-073 Decision 5).
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=CharacterVoiceDriftDeps,
            output_type=VoiceDriftResult,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[CharacterVoiceDriftDeps],
        output: VoiceDriftResult,
    ) -> VoiceDriftResult:
        """Validate deterministic invariants for voice-drift output.

        ADR-035: enforces output quality at the agent boundary. No side effects
        — deterministic validation/cleanup only.

        Invariants:
        - ``confidence`` bounds (0.0-1.0) are enforced by the Pydantic Field
          (out-of-range values raise ``ValidationError`` before the validator
          runs — mirroring the checker's ``qualitative_sub_score``).
        - ``drift_type`` is one of the three literals (enforced by Pydantic).
        - ``per_chapter_notes`` entries with an empty ``chapter_id`` are
          filtered out (a note without a chapter anchor is useless to the
          caller). The list may legitimately be empty (stable voice).
        - ``suggested_attention`` / ``longitudinal_reasons`` empty/whitespace
          strings are filtered out (no padding).

        Unlike the checker, this never raises :class:`~pydantic_ai.ModelRetry`:
        the output is a single result (always present), and both
        ``per_chapter_notes`` and ``suggested_attention`` are legitimately
        empty for a stable voice (ADR-073 Decision 5 graceful — the template's
        empty-trend convention yields ``confidence=0.0`` + empty lists, which
        is a valid result, not a retry).
        """
        valid_notes = [n for n in output.per_chapter_notes if n.chapter_id.strip()]
        valid_reasons = [r for r in output.longitudinal_reasons if r.strip()]
        valid_attention = [c for c in output.suggested_attention if c.strip()]
        return output.model_copy(
            update={
                "per_chapter_notes": valid_notes,
                "longitudinal_reasons": valid_reasons,
                "suggested_attention": valid_attention,
            }
        )

    async def run(
        self,
        prompt: str,
        deps: CharacterVoiceDriftDeps,
        **kwargs: Any,
    ) -> VoiceDriftResult:
        """Execute the voice-drift agent and return structured output."""
        return await super().run(prompt, deps, **kwargs)
