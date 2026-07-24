"""Dialogue-coach Pydantic Evals dataset (RULE-18b weight-effect evidence).

Each case supplies a dialogue passage with a **known voice mismatch** and a
descriptive voice profile that contradicts it. The eval task runs the
``DialogueCoachAgent`` twice — once with the voice profiles included (high
``voice_fidelity``) and once with them suppressed (low ``voice_fidelity``).
The evaluator asserts that the ``voice_mismatch`` issue count differs
between the two runs.

Per ADR-069 RULE-18b: ``AdaptiveWeights`` effect-integrity is proven when
changing a weight measurably changes output. This dataset provides the
inputs; the task provides the mechanism; the evaluator provides the assertion.
"""

from __future__ import annotations

from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance

from evals.evaluators.dialogue_coach import (
    DialogueCoachOutputStructure,
    VoiceFidelityWeightEffect,
)
from evals.models_dialogue_coach import DialogueCoachEvalInput, DialogueCoachEvalResult


def build_dataset() -> Dataset[DialogueCoachEvalInput, DialogueCoachEvalResult, dict[str, Any]]:
    """Build the dialogue_coach eval dataset.

    Cases cover different mismatch archetypes — a terse character speaking
    formally, a formal character using slang, and a character whose
    vocabulary register clashes with their established profile. Each case's
    ``metadata`` carries the expected high-fidelity voice_mismatch count so
    the runtime evaluator can assert effect strength.
    """

    return Dataset(
        name="dialogue_coach",
        cases=[
            Case(
                name="terse-character-formal-speech",
                inputs=DialogueCoachEvalInput(
                    dialogue_passage=(
                        '"Good morning, esteemed colleagues. I trust you '
                        'are all in fine spirits this day," Alice said. '
                        '"Indeed, the proceedings have been most '
                        'illuminating thus far."'
                    ),
                    voice_profiles_text=(
                        "Alice: Terse and direct. Speaks in short, clipped "
                        "sentences. Rarely uses more than six words. Avoids "
                        "formal register entirely — never says 'esteemed', "
                        "'proceedings', or 'spirits'."
                    ),
                    characters=["Alice"],
                ),
                expected_output=None,
                metadata={
                    "expected_high_mismatch_count": 1,
                    "expected_low_mismatch_count": 0,
                },
            ),
            Case(
                name="formal-character-slang",
                inputs=DialogueCoachEvalInput(
                    dialogue_passage=(
                        "\"Yeah nah, that ain't gonna fly, bro. You gotta "
                        'chill and let me handle this, ya dig?" Bob said '
                        "with a shrug."
                    ),
                    voice_profiles_text=(
                        "Bob: Highly formal and precise. Uses complete "
                        "sentences with subordinate clauses. Never "
                        "contracts words. Speaks in the register of an "
                        "academic — avoids slang, colloquialisms, and "
                        "filler words entirely."
                    ),
                    characters=["Bob"],
                ),
                expected_output=None,
                metadata={
                    "expected_high_mismatch_count": 1,
                    "expected_low_mismatch_count": 0,
                },
            ),
            Case(
                name="vocabulary-register-clash",
                inputs=DialogueCoachEvalInput(
                    dialogue_passage=(
                        '"I reckon we should utilize the aforementioned '
                        'methodology to facilitate optimal outcomes," '
                        'Clara said. "Furthermore, it is incumbent upon '
                        'us to leverage synergistic paradigms."'
                    ),
                    voice_profiles_text=(
                        "Clara: Plain-spoken and warm. Uses everyday "
                        "vocabulary. Favour concrete nouns over abstract "
                        "jargon. Would never say 'utilize', 'aforementioned', "
                        "'methodology', 'facilitate', 'paradigms', or "
                        "'synergistic'. Her speech sounds like a friend "
                        "talking, not a consultant."
                    ),
                    characters=["Clara"],
                ),
                expected_output=None,
                metadata={
                    "expected_high_mismatch_count": 1,
                    "expected_low_mismatch_count": 0,
                },
            ),
        ],
        evaluators=[
            IsInstance(type_name="DialogueCoachEvalResult"),
            DialogueCoachOutputStructure(),
            VoiceFidelityWeightEffect(),
        ],
    )
