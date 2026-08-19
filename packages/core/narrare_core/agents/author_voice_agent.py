"""AuthorVoiceAgent — NarrareAgent for qualitative author-voice profiling
(ANAL-007 / ADR-074).

The qualitative half of ADR-074's hybrid metrics strategy (the structural
parallel to ANAL-008's :class:`CharacterVoiceAgent`). A single LLM call
profiles the narrator's voice by interpreting the chapter prose together with
the deterministic
:class:`~narrare_core.schemas.voice.VoiceMetrics` (computed by
:meth:`~narrare_core.analysis.voice_metrics.VoiceMetricsAnalyzer.analyze_text`)
and the deterministic
:class:`~narrare_core.analysis.author_metrics.AuthorMetrics` (computed by
:class:`~narrare_core.analysis.author_metrics.AuthorMetricsAnalyzer`). The
agent produces :class:`~narrare_core.agents.author_voice_types.AuthorVoiceOutput`
— descriptive-only structured output mirroring the governed ``author_voice``
template's JSON contract.

Binding boundary (ADR-074 — binding): the agent NEVER produces
``VoiceMetrics`` or ``AuthorMetrics``. Measurement is deterministic, done by
the analyzers; the agent ONLY interprets qualitatively. This keeps the ADR-021
determinism guarantee intact (metrics stable across runs for Phase 2B drift
comparability) and preserves the descriptive/metric boundary.

Prompt loading (RULE-02b): the governed ``author_voice`` template IS the
system prompt. It is resolved Mode 1 by the Layer-3 service via
:class:`~narrare_core.prompts.composer.PromptComposer` and passed to this
agent's constructor as ``system_prompt``. The agent itself contains NO inline
system prompt — it never builds prompts with f-strings (RULE-02). The run
prompt (user channel) carries the prose excerpt + precomputed metrics as
category-3 runtime content (RULE-02a).

RULE-13 (ADR-065): ``run()`` returns the structured
:class:`AuthorVoiceOutput`; streaming is inherited from
:class:`~narrare_core.agents.base.NarrareAgent` (``run_stream()``) — mirrors
the sibling :class:`CharacterVoiceAgent` / :class:`CharacterVoiceDriftAgent`.

Usage::

    model = await registry.get_model(config)
    agent = AuthorVoiceAgent(
        model=model,
        system_prompt=resolved_template_system,  # from PromptComposer Mode 1
    )
    deps = AuthorVoiceDeps(
        chapter_prose="The wind moved through the grass. ...",
        voice_metrics_summary="avg_sent_len=14.3, ttr=0.71, ...",
        author_metrics_summary="dialogue_ratio=0.42, metaphor_density=0.03",
        writing_language="en",
    )
    result = await agent.run(
        prompt=(
            f"Prose:\\n{deps.chapter_prose}\\n\\n"
            f"Voice metrics:\\n{deps.voice_metrics_summary}\\n\\n"
            f"Author metrics:\\n{deps.author_metrics_summary}"
        ),
        deps=deps,
    )
    print(result.formality, result.vocabulary_level, result.author_examples)

See Also
--------
ADR-074 — Author Voice Storage Contract (boundary invariant).
ADR-035 — Agent output validation.
ADR-054 — Mode-1 PromptComposer mandate.
"""

from __future__ import annotations

from typing import Any

# RunContext is intentionally a RUNTIME import (not TYPE_CHECKING): pydantic-ai
# evaluates the output function's type hints via typing.get_type_hints() at
# agent-construction time, so the annotation ``ctx: RunContext[...]`` MUST
# resolve at runtime. Mirrors CharacterVoiceDriftAgent. noqa: TC002.
from pydantic_ai import RunContext  # noqa: TC002

from narrare_core.agents.author_voice_types import (
    AuthorVoiceDeps,
    AuthorVoiceOutput,
    EmotionalRange,
    SentenceProfile,
    VocabularyLevel,
)
from narrare_core.agents.base import NarrareAgent


class AuthorVoiceAgent(NarrareAgent[AuthorVoiceDeps, AuthorVoiceOutput]):
    """Agent for qualitative author-voice profiling.

    Takes chapter prose (the narrator's full text) + precomputed deterministic
    voice metrics + precomputed author-specific prose-level metrics and produces
    a single qualitative author-voice profile (formality register, vocabulary
    level, sentence profile, emotional range, cultural/regional markers, and
    curated representative prose passages).

    The deterministic metrics are supplied to the model as runtime content —
    the agent interprets them, never recomputes them (ADR-074 binding +
    ADR-021). It produces DESCRIPTIVE output only (binding boundary).
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=AuthorVoiceDeps,
            output_type=[self._process_output, AuthorVoiceOutput],
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[AuthorVoiceDeps],
        output: AuthorVoiceOutput,
    ) -> AuthorVoiceOutput:
        """Validate deterministic invariants for author-voice output.

        ADR-035: enforces output quality at the agent boundary. No side effects
        — deterministic validation/cleanup only.

        Invariants:
        - ``formality`` bounds (0.0-1.0) are enforced by the Pydantic Field
          (out-of-range values raise ``ValidationError`` before this validator
          runs — mirroring CharacterVoiceAgent / VoiceDriftAgent).
        - The vocabulary / sentence / emotional-range literals are enforced by
          Pydantic.
        - ``cultural_regional_markers`` is normalized to ``None`` when empty/
          whitespace (an empty marker is not useful to the caller or the
          renderer).
        - ``author_examples`` entries that are empty/whitespace are filtered
          out (no padding).

        Unlike :class:`CharacterVoiceAgent`, this never raises
        :class:`~pydantic_ai.ModelRetry`: author voice is always a single
        result (always present), and an empty examples list is a valid output
        (the prose under analysis may be too short for a curated excerpt).
        """
        cleaned_markers = output.cultural_regional_markers
        if cleaned_markers is not None and not cleaned_markers.strip():
            cleaned_markers = None

        cleaned_examples = [e for e in output.author_examples if e.strip()]

        return output.model_copy(
            update={
                "cultural_regional_markers": cleaned_markers,
                "author_examples": cleaned_examples,
            }
        )

    async def _process_output(
        self,
        ctx: RunContext[AuthorVoiceDeps],
        formality: float = 0.5,
        vocabulary_level: VocabularyLevel = "moderate",
        sentence_profile: SentenceProfile = "medium",
        emotional_range: EmotionalRange = "moderate",
        cultural_regional_markers: str | None = None,
        author_examples: list[str] | None = None,
    ) -> AuthorVoiceOutput:
        """Output Function — structures the LLM response into AuthorVoiceOutput.

        During streaming (``ctx.partial_output``) returns a minimal default
        result (mirrors the sibling agents' partial-output convention).
        """
        if ctx.partial_output:
            return AuthorVoiceOutput()

        return AuthorVoiceOutput(
            formality=formality,
            vocabulary_level=vocabulary_level,
            sentence_profile=sentence_profile,
            emotional_range=emotional_range,
            cultural_regional_markers=cultural_regional_markers,
            author_examples=author_examples or [],
        )

    async def run(
        self,
        prompt: str,
        deps: AuthorVoiceDeps,
        **kwargs: Any,
    ) -> AuthorVoiceOutput:
        """Execute the author-voice agent and return structured output.

        Args:
            prompt: The agent run prompt (user channel, RULE-02a category 3).
                Carries the prose excerpt + precomputed metrics summary as
                runtime content; never a system/task instruction.
            deps: Author-voice dependencies (carries the same data for
                structured access).
            **kwargs: Passed through to ``pydantic_ai.Agent.run``.

        Returns:
            The structured :class:`AuthorVoiceOutput` (descriptive-only —
            binding boundary enforced at the output-type level).
        """
        return await super().run(prompt, deps, **kwargs)
