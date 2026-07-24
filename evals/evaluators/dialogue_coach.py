"""Deterministic evaluators for the ``dialogue_coach`` eval suite.

Two evaluators verify the RULE-18b evidence harness:

- ``DialogueCoachOutputStructure`` — structural correctness: both runs
  produced valid ``DialogueCoachWeightResult`` objects with non-negative
  counts. Scores 1.0 when the structure is sound, 0.0 otherwise.

- ``VoiceFidelityWeightEffect`` — the RULE-18b assertion: changing
  ``voice_fidelity`` from 1.0 to 0.1 measurably changes the
  ``voice_mismatch`` issue count. Scores 1.0 when
  ``high_fidelity.voice_mismatch_count != low_fidelity.voice_mismatch_count``
  (or when the metadata-pinned expected counts match in smoke mode).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from evals.models_dialogue_coach import DialogueCoachEvalResult


@dataclass
class DialogueCoachOutputStructure(Evaluator[Any, DialogueCoachEvalResult, dict[str, Any]]):
    """Structural correctness check (deterministic, smoke yields 1.0).

    Verifies that both weight runs produced valid results with sensible
    non-negative counts. This is the smoke-mode invariant — if the task
    runs without error and returns the right structure, this scores 1.0.

    Weighting:
      * 0.4 — both ``voice_fidelity`` values match the expected constants.
      * 0.3 — ``voice_profiles_included`` is True for high, False for low.
      * 0.3 — all counts are non-negative integers.
    """

    def evaluate(
        self, ctx: EvaluatorContext[Any, DialogueCoachEvalResult, dict[str, Any]]
    ) -> float:
        result = ctx.output
        high = result.high_fidelity
        low = result.low_fidelity

        weight_score = 1.0 if high.voice_fidelity == 1.0 and low.voice_fidelity == 0.1 else 0.0

        inclusion_score = (
            1.0 if high.voice_profiles_included and not low.voice_profiles_included else 0.0
        )

        counts_ok = all(
            c >= 0
            for c in (
                high.voice_mismatch_count,
                high.total_issue_count,
                low.voice_mismatch_count,
                low.total_issue_count,
            )
        )
        count_score = 1.0 if counts_ok else 0.0

        return (weight_score * 0.4) + (inclusion_score * 0.3) + (count_score * 0.3)


@dataclass
class VoiceFidelityWeightEffect(Evaluator[Any, DialogueCoachEvalResult, dict[str, Any]]):
    """RULE-18b assertion: weight change produces observable output change.

    Scores 1.0 when the ``voice_mismatch`` count differs between the
    high-fidelity and low-fidelity runs. This is the core RULE-18b evidence
    point — it proves ``AdaptiveWeights`` has measurable effect on LLM
    behaviour.

    In smoke mode (TestModel), the task simulates the effect by injecting
    different ``custom_output_args`` for each run. In runtime mode, the
    real LLM responds to the prompt difference (voice profiles included vs
    suppressed) and naturally produces different issue counts.

    When ``metadata`` carries pinned expected counts
    (``expected_high_mismatch_count`` / ``expected_low_mismatch_count``),
    the evaluator additionally checks those match — a stricter assertion
    for runtime mode.
    """

    def evaluate(
        self, ctx: EvaluatorContext[Any, DialogueCoachEvalResult, dict[str, Any]]
    ) -> float:
        result = ctx.output
        high_count = result.high_fidelity.voice_mismatch_count
        low_count = result.low_fidelity.voice_mismatch_count

        # Core RULE-18b assertion: counts differ.
        differs = high_count != low_count

        # Optional stricter check against pinned metadata expectations.
        meta = ctx.metadata or {}
        expected_high = meta.get("expected_high_mismatch_count")
        expected_low = meta.get("expected_low_mismatch_count")
        if expected_high is not None and expected_low is not None:
            # When expectations are pinned, require exact match + difference.
            if high_count == expected_high and low_count == expected_low and differs:
                return 1.0
            return 0.0

        return 1.0 if differs else 0.0
