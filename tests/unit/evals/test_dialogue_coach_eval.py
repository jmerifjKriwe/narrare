"""Structural tests for the ``dialogue_coach`` eval suite (RULE-18b).

These tests verify the eval task STRUCTURE without calling a real LLM:

- The smoke task runs via TestModel and produces valid output.
- The weight-effect observation logic is correct (high != low counts).
- The evaluators score as expected on valid/invalid output.
- The dataset factory builds with the right structure.
- The task is registered in both smoke and runtime factories.

Per ADR-069 RULE-18b: this is the structural harness. The REAL behavioural
evidence (LLM produces different counts) is collected in runtime mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import pytest
from evals.datasets.dialogue_coach import build_dataset
from evals.evaluators.dialogue_coach import (
    DialogueCoachOutputStructure,
    VoiceFidelityWeightEffect,
)
from evals.models_dialogue_coach import (
    HIGH_FIDELITY_WEIGHT,
    LOW_FIDELITY_WEIGHT,
    DialogueCoachEvalInput,
    DialogueCoachEvalResult,
    DialogueCoachWeightResult,
)
from evals.tasks import available_suites_for_mode, get_task

if TYPE_CHECKING:
    from pydantic_evals.evaluators import EvaluatorContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Ctx:
    """Small evaluator context double with only fields our evaluators read."""

    output: Any
    metadata: dict[str, Any] | None = None


def _ctx(
    *,
    output: Any,
    metadata: dict[str, Any] | None = None,
) -> EvaluatorContext[Any, Any, dict[str, Any]]:
    return cast(
        "EvaluatorContext[Any, Any, dict[str, Any]]", _Ctx(output=output, metadata=metadata)
    )


def _sample_input() -> DialogueCoachEvalInput:
    """Return a minimal eval input with a known voice mismatch."""

    return DialogueCoachEvalInput(
        dialogue_passage='"Good morning, esteemed colleagues," Alice said.',
        voice_profiles_text="Alice: Terse. Never says 'esteemed' or 'colleagues'.",
        characters=["Alice"],
    )


def _make_result(
    *,
    high_vm: int = 1,
    low_vm: int = 0,
    high_total: int | None = None,
    low_total: int | None = None,
) -> DialogueCoachEvalResult:
    """Build a DialogueCoachEvalResult with the given mismatch counts."""

    return DialogueCoachEvalResult(
        high_fidelity=DialogueCoachWeightResult(
            voice_fidelity=HIGH_FIDELITY_WEIGHT,
            voice_profiles_included=True,
            voice_mismatch_count=high_vm,
            total_issue_count=high_total if high_total is not None else high_vm,
        ),
        low_fidelity=DialogueCoachWeightResult(
            voice_fidelity=LOW_FIDELITY_WEIGHT,
            voice_profiles_included=False,
            voice_mismatch_count=low_vm,
            total_issue_count=low_total if low_total is not None else low_vm,
        ),
        weight_effect_observed=high_vm != low_vm,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestDialogueCoachRegistration:
    """The suite is registered in both smoke and runtime factories."""

    def test_registered_in_smoke_suites(self) -> None:
        assert "dialogue_coach" in available_suites_for_mode("smoke")

    def test_registered_in_runtime_suites(self) -> None:
        assert "dialogue_coach" in available_suites_for_mode("runtime")

    def test_smoke_task_is_callable(self) -> None:
        assert callable(get_task("dialogue_coach", "smoke"))

    def test_runtime_task_is_callable(self) -> None:
        assert callable(get_task("dialogue_coach", "runtime"))


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------


class TestDialogueCoachDataset:
    """The dataset builds with the expected structure."""

    def test_dataset_has_cases(self) -> None:
        dataset = build_dataset()
        assert len(dataset.cases) >= 1

    def test_each_case_has_voice_mismatch_setup(self) -> None:
        dataset = build_dataset()
        for case in dataset.cases:
            inputs: DialogueCoachEvalInput = case.inputs  # type: ignore[assignment]
            assert inputs.dialogue_passage
            assert inputs.voice_profiles_text

    def test_each_case_has_expected_counts_metadata(self) -> None:
        dataset = build_dataset()
        for case in dataset.cases:
            meta = case.metadata or {}
            assert "expected_high_mismatch_count" in meta
            assert "expected_low_mismatch_count" in meta


# ---------------------------------------------------------------------------
# Smoke task (TestModel-based)
# ---------------------------------------------------------------------------


class TestDialogueCoachSmokeTask:
    """The smoke task runs the agent via TestModel and produces valid output."""

    @pytest.mark.asyncio
    async def test_smoke_task_produces_valid_result(self) -> None:
        result = await get_task("dialogue_coach", "smoke")(_sample_input())
        assert isinstance(result, DialogueCoachEvalResult)

    @pytest.mark.asyncio
    async def test_high_fidelity_has_more_mismatches_than_low(self) -> None:
        """In smoke mode, high fidelity simulates detection, low simulates none."""

        result = await get_task("dialogue_coach", "smoke")(_sample_input())
        assert result.high_fidelity.voice_mismatch_count > 0
        assert result.low_fidelity.voice_mismatch_count == 0
        assert result.weight_effect_observed is True

    @pytest.mark.asyncio
    async def test_high_fidelity_includes_voice_profiles(self) -> None:
        result = await get_task("dialogue_coach", "smoke")(_sample_input())
        assert result.high_fidelity.voice_profiles_included is True
        assert result.low_fidelity.voice_profiles_included is False

    @pytest.mark.asyncio
    async def test_weight_values_match_constants(self) -> None:
        result = await get_task("dialogue_coach", "smoke")(_sample_input())
        assert result.high_fidelity.voice_fidelity == HIGH_FIDELITY_WEIGHT
        assert result.low_fidelity.voice_fidelity == LOW_FIDELITY_WEIGHT

    @pytest.mark.asyncio
    async def test_total_issue_count_ge_mismatch_count(self) -> None:
        result = await get_task("dialogue_coach", "smoke")(_sample_input())
        assert result.high_fidelity.total_issue_count >= result.high_fidelity.voice_mismatch_count
        assert result.low_fidelity.total_issue_count >= result.low_fidelity.voice_mismatch_count


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------


class TestDialogueCoachOutputStructureEvaluator:
    """The structure evaluator checks weight values, inclusion flags, counts."""

    def test_valid_structure_scores_one(self) -> None:
        score = DialogueCoachOutputStructure().evaluate(_ctx(output=_make_result()))
        assert score == 1.0

    def test_wrong_weight_values_reduce_score(self) -> None:
        result = DialogueCoachEvalResult(
            high_fidelity=DialogueCoachWeightResult(
                voice_fidelity=0.5,  # wrong — should be 1.0
                voice_profiles_included=True,
            ),
            low_fidelity=DialogueCoachWeightResult(
                voice_fidelity=0.1,
                voice_profiles_included=False,
            ),
        )
        score = DialogueCoachOutputStructure().evaluate(_ctx(output=result))
        # 0.0*0.4 (weight) + 1.0*0.3 (inclusion) + 1.0*0.3 (counts) = 0.6
        assert score == pytest.approx(0.6)

    def test_wrong_inclusion_flags_reduce_score(self) -> None:
        result = DialogueCoachEvalResult(
            high_fidelity=DialogueCoachWeightResult(
                voice_fidelity=1.0,
                voice_profiles_included=False,  # wrong — should be True
            ),
            low_fidelity=DialogueCoachWeightResult(
                voice_fidelity=0.1,
                voice_profiles_included=True,  # wrong — should be False
            ),
        )
        score = DialogueCoachOutputStructure().evaluate(_ctx(output=result))
        # 1.0*0.4 (weight) + 0.0*0.3 (inclusion) + 1.0*0.3 (counts) = 0.7
        assert score == pytest.approx(0.7)


class TestVoiceFidelityWeightEffectEvaluator:
    """The weight-effect evaluator asserts high != low mismatch counts."""

    def test_differing_counts_score_one(self) -> None:
        score = VoiceFidelityWeightEffect().evaluate(_ctx(output=_make_result(high_vm=2, low_vm=0)))
        assert score == 1.0

    def test_equal_counts_score_zero(self) -> None:
        score = VoiceFidelityWeightEffect().evaluate(_ctx(output=_make_result(high_vm=1, low_vm=1)))
        assert score == 0.0

    def test_both_zero_score_zero(self) -> None:
        score = VoiceFidelityWeightEffect().evaluate(_ctx(output=_make_result(high_vm=0, low_vm=0)))
        assert score == 0.0

    def test_pinned_metadata_exact_match_scores_one(self) -> None:
        score = VoiceFidelityWeightEffect().evaluate(
            _ctx(
                output=_make_result(high_vm=1, low_vm=0),
                metadata={"expected_high_mismatch_count": 1, "expected_low_mismatch_count": 0},
            )
        )
        assert score == 1.0

    def test_pinned_metadata_mismatch_scores_zero(self) -> None:
        score = VoiceFidelityWeightEffect().evaluate(
            _ctx(
                output=_make_result(high_vm=1, low_vm=0),
                metadata={"expected_high_mismatch_count": 2, "expected_low_mismatch_count": 0},
            )
        )
        assert score == 0.0
