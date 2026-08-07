"""AuthorVoiceDriftAgent — NarrareAgent for longitudinal narrator-voice drift
classification (ANAL-009 Phase 2B / ADR-074).

The author-voice analogue of Phase 1's
:class:`~narrare_core.agents.character_voice_drift_agent.CharacterVoiceDriftAgent`.
A single LLM call classifies the longitudinal **narrator-voice** drift across
chapters by interpreting (a) the stored *descriptive* author-voice profile
(:class:`~narrare_core.profiles.author_voice.AuthorVoiceProfile`'s descriptive
group), (b) a precomputed per-chapter match trend (signal i) whose deltas
MERGE voice-generic + author-specific metrics, and (c) detected adjacent-
chapter jump points (signal iii) — all supplied as runtime context. The agent
produces the REUSED
:class:`~narrare_core.agents.character_voice_drift_types.VoiceDriftResult`
(the same locked output contract as the character drift agent).

Measurement is already done by
:mod:`narrare_core.analysis.author_voice_drift_scoring` (deterministic,
ADR-021); the agent ONLY interprets the trend qualitatively (ADR-021 hybrid
tier — mirrors ANAL-003/008/057/073). It never recomputes metrics, distances,
or bands.

Decision 5 scope boundary (same as the character agent): this agent is
**read-only classification only**. It does NOT suggest rewrites (WRITE-004)
and does NOT build/update an author-voice profile (ANAL-007). The reused
:class:`VoiceDriftResult` therefore carries no rewrite or profile field.

Prompt loading (RULE-02b): the governed ``author_voice_drift`` template IS
the system prompt. It is resolved Mode 1 by the Layer-3 service via
:class:`~narrare_core.prompts.composer.PromptComposer` and passed to this
agent's constructor as ``system_prompt``. The agent itself contains NO inline
system prompt — it never builds prompts with f-strings (RULE-02). The run
prompt (user channel) carries the descriptive profile + precomputed trend +
jumps + chapter metadata as category-3 runtime content (RULE-02a).

RULE-13 (ADR-065): ``run()`` returns the structured
:class:`VoiceDriftResult`; streaming is inherited from
:class:`~narrare_core.agents.base.NarrareAgent` (``run_stream()``) — mirrors
the sibling :class:`CharacterVoiceDriftAgent` / :class:`AuthorVoiceAgent`.

Usage::

    model = await registry.get_model(config)
    agent = AuthorVoiceDriftAgent(
        model=model,
        system_prompt=resolved_template_system,  # from PromptComposer Mode 1
    )
    deps = AuthorVoiceDriftDeps(
        descriptive_profile=render_author_voice_for_generation(profile),
        trend=trend_points,        # from trend_against_author_profile()
        jumps=jump_points,         # from detect_adjacent_author_jumps()
        chapter_meta=[ChapterMeta(chapter_id="ch-1", title="The Arrival")],
        writing_language="en",
    )
    result = await agent.run(
        prompt=(
            f"Stored author profile:\\n{deps.descriptive_profile}\\n\\n"
            f"Trend:\\n{format_trend(deps.trend)}\\n\\n"
            f"Jumps:\\n{format_jumps(deps.jumps)}\\n\\n"
            f"Chapters:\\n{format_meta(deps.chapter_meta)}"
        ),
        deps=deps,
    )
    print(result.drift_type, result.confidence, result.suggested_attention)

See Also
--------
    ADR-074 — Author Voice Storage Contract.
    ADR-073 — Character Voice Drift (Decision 3 agent role, Decision 5 scope).
    ADR-035 — Agent output validation.
    ADR-054 — Mode-1 PromptComposer mandate.
    narrare_core.analysis.author_voice_drift_scoring — the precomputed trend
        + jumps (author-metric deltas merged into per_metric_deltas).
"""

from __future__ import annotations

from typing import Any

# RunContext is intentionally a RUNTIME import (not TYPE_CHECKING): pydantic-ai
# evaluates the output function's type hints via typing.get_type_hints() at
# agent-construction time, so the annotation ``ctx: RunContext[...]`` MUST
# resolve at runtime. Mirrors CharacterVoiceDriftAgent. noqa: TC002.
from pydantic_ai import RunContext  # noqa: TC002

from narrare_core.agents.author_voice_drift_types import AuthorVoiceDriftDeps
from narrare_core.agents.base import NarrareAgent

# OUTPUT shape is REUSED — the narrator trend is classified into the same
# locked contract as the character trend (the task's "reuse VoiceDriftResult
# shape" mandate; ADR-073 D3 locked shape, applied to ADR-074 author voice).
from narrare_core.agents.character_voice_drift_types import (
    ChapterNote,
    VoiceDriftResult,
)


class AuthorVoiceDriftAgent(NarrareAgent[AuthorVoiceDriftDeps, VoiceDriftResult]):
    """Agent for longitudinal narrator-voice drift classification.

    Takes the stored descriptive author-voice profile + a precomputed
    per-chapter match trend (voice + author deltas merged) + detected
    adjacent-chapter jump points + chapter metadata (all runtime content) and
    produces a single qualitative classification: a ``drift_type``
    (evolution / context / inconsistency), a confidence, the longitudinal
    reasons that drove the classification, sparse per-chapter notes, and the
    chapter ids most worth the author's review.

    The trend + jumps are supplied to the model as runtime content — the agent
    interprets them, never recomputes them (ADR-021/ADR-074). It does not
    suggest rewrites and does not build a profile (Decision 5 scope).
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=AuthorVoiceDriftDeps,
            output_type=[self._process_output, VoiceDriftResult],
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[AuthorVoiceDriftDeps],
        output: VoiceDriftResult,
    ) -> VoiceDriftResult:
        """Validate deterministic invariants for author-voice-drift output.

        Identical contract to :meth:`CharacterVoiceDriftAgent._validate_output`
        (the output shape is reused). ADR-035: enforces output quality at the
        agent boundary. No side effects — deterministic validation/cleanup only.

        Invariants:
        - ``confidence`` bounds (0.0-1.0) are enforced by the Pydantic Field.
        - ``drift_type`` is one of the three literals (enforced by Pydantic).
        - ``per_chapter_notes`` entries with an empty ``chapter_id`` are
          filtered out. The list may legitimately be empty (stable voice).
        - ``suggested_attention`` / ``longitudinal_reasons`` empty/whitespace
          strings are filtered out (no padding).

        Never raises :class:`~pydantic_ai.ModelRetry`: the output is a single
        result (always present), and both ``per_chapter_notes`` and
        ``suggested_attention`` are legitimately empty for a stable narrator
        voice (the template's empty-trend convention yields ``confidence=0.0``
        + empty lists, which is a valid result, not a retry).
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

    async def _process_output(
        self,
        ctx: RunContext[AuthorVoiceDriftDeps],
        drift_type: str = "evolution",
        confidence: float = 0.0,
        longitudinal_reasons: list[str] | None = None,
        per_chapter_notes: list[dict[str, Any]] | None = None,
        suggested_attention: list[str] | None = None,
    ) -> VoiceDriftResult:
        """Output Function — structures the LLM response into VoiceDriftResult.

        During streaming (``ctx.partial_output``) returns a minimal empty result.
        """
        if ctx.partial_output:
            return VoiceDriftResult()

        return VoiceDriftResult(
            drift_type=drift_type,  # type: ignore[arg-type]
            confidence=confidence,
            longitudinal_reasons=longitudinal_reasons or [],
            per_chapter_notes=[ChapterNote(**note) for note in (per_chapter_notes or [])],
            suggested_attention=suggested_attention or [],
        )

    async def run(
        self,
        prompt: str,
        deps: AuthorVoiceDriftDeps,
        **kwargs: Any,
    ) -> VoiceDriftResult:
        """Execute the author-voice-drift agent and return structured output."""
        return await super().run(prompt, deps, **kwargs)
