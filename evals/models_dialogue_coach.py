"""Typed case inputs and outputs for the ``dialogue_coach`` eval suite.

Extracted from ``evals/models.py`` per RULE-04 (modularize, do not compress),
mirroring ``models_writing.py`` / ``models_names.py``. The models are
re-exported from ``evals.models`` so existing imports keep working.

This suite is the **RULE-18b evidence harness** (ADR-069): it proves that
``AdaptiveWeights.voice_fidelity`` has an observable effect on LLM behaviour.
The eval runs the ``DialogueCoachAgent`` twice on the same dialogue passage:

- **High fidelity** (``voice_fidelity=1.0``): the full descriptive voice
  profiles text is injected into the prompt. With a strong voice reference
  the model detects ``voice_mismatch`` issues.
- **Low fidelity** (``voice_fidelity=0.1``): the voice profiles text is
  suppressed (empty string). Without a voice reference the model detects
  fewer or zero ``voice_mismatch`` issues.

The weight *gates the inclusion* of the signal — this is the mechanism by
which ``voice_fidelity`` has observable effect, as mandated by
``AdaptiveWeights``' contract ("a higher weight controls how strongly the
corresponding signal is injected into the prompt").
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = [
    "DialogueCoachEvalInput",
    "DialogueCoachEvalResult",
    "DialogueCoachWeightResult",
]

# The two voice_fidelity weight values exercised by every case.
# These are the RULE-18b evidence points — changing between them must
# produce measurably different output.
HIGH_FIDELITY_WEIGHT: float = 1.0
LOW_FIDELITY_WEIGHT: float = 0.1


class DialogueCoachEvalInput(BaseModel):
    """Input for the dialogue_coach eval (RULE-18b weight-effect evidence).

    Attributes:
        dialogue_passage: A dialogue passage containing known voice
            mismatches (a character speaks in a register that contradicts
            their established voice profile).
        voice_profiles_text: Descriptive voice profiles text that
            contradicts the passage. When included (high fidelity), the
            LLM can detect voice mismatches; when suppressed (low
            fidelity), it cannot.
        characters: Canonical speaker roster (from DialogueParser
            attribution).
        project_title: Project title (prompt context).
        genre: Project genre (prompt context).
        language: Writing language code.
    """

    dialogue_passage: str = Field(min_length=1)
    voice_profiles_text: str = Field(min_length=1)
    characters: list[str] = Field(default_factory=list)
    project_title: str = "Eval Novel"
    genre: str = "Fantasy"
    language: str = "en"


class DialogueCoachWeightResult(BaseModel):
    """Result of one DialogueCoachAgent run at a specific weight.

    Attributes:
        voice_fidelity: The weight value used for this run.
        voice_profiles_included: Whether the voice profiles text was
            included in the prompt (True for high fidelity, False for
            low fidelity).
        voice_mismatch_count: Number of ``voice_mismatch`` issues detected.
        total_issue_count: Total number of issues detected (all types).
    """

    voice_fidelity: float
    voice_profiles_included: bool
    voice_mismatch_count: int = 0
    total_issue_count: int = 0


class DialogueCoachEvalResult(BaseModel):
    """Comparison result of two DialogueCoachAgent runs (RULE-18b evidence).

    Carries the high-fidelity and low-fidelity results side by side so the
    evaluator can assert that changing ``voice_fidelity`` produced a
    measurable difference in ``voice_mismatch`` detection.

    Attributes:
        high_fidelity: Result at ``voice_fidelity=1.0`` (full voice profiles).
        low_fidelity: Result at ``voice_fidelity=0.1`` (voice profiles
            suppressed).
        weight_effect_observed: True when the ``voice_mismatch_count``
            differs between the two runs. In smoke mode (TestModel), this
            reflects the simulated effect; in runtime mode it reflects the
            real LLM's behavioural response to the weight change.
    """

    high_fidelity: DialogueCoachWeightResult
    low_fidelity: DialogueCoachWeightResult
    weight_effect_observed: bool = False
