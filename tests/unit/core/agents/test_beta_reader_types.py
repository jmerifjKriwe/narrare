"""Data-contract tests for BetaReaderAgent output types.

2026-09-14 real eval run (``2026-09-14-168945f4-1``) measured two Phase-2
contract violations on a German chapter:

1. ``detailed_feedback`` severities drifted to German ("mittel"/"hoch"/
   "niedrig") — the output model carried a free-string ``severity`` field
   and the template did not pin the English literals.
2. ``revision_suggestions`` count 8 violated the 3-6 contract.

The schema now enforces both invariants (Literal severity + count
field_validator, mirroring the public ``FeedbackSeverity`` contract), so
pydantic-ai retries invalid outputs instead of shipping them (ADR-035).
The template-side pins are covered separately in
``tests/unit/core/prompts/test_deepdive_prompt_render.py``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.agents.beta_reader_types import (
    MAX_REVISION_SUGGESTIONS,
    MIN_REVISION_SUGGESTIONS,
    AgentDeepDiveFeedback,
    AgentFeedbackItem,
    BetaReaderPhase2Output,
)

# The German drift measured in eval run 2026-09-14-168945f4-1.
_GERMAN_SEVERITIES = ("kritisch", "mittel", "hoch", "niedrig")

_ENGLISH_SEVERITIES = ("critical", "moderate", "minor")

#: Every case is built via ``model_validate`` on plain dicts — invalid
#: inputs flow through validation without static-type suppressions
#: (RULE-23).
_P1_FEEDBACK_ARGS: dict[str, str] = {
    "category": "pacing",
    "severity": "moderate",
    "title": "Dragging middle",
    "description": "The middle section repeats its beats.",
}

_P2_DEEPDIVE_ARGS: dict[str, str] = {
    "category": "character",
    "severity": "moderate",
    "title": "Flat character",
    "description": "Bob lacks depth.",
}


def _suggestions(count: int) -> list[str]:
    return [f"Revision step {index}" for index in range(1, count + 1)]


def _phase2_args(suggestion_count: int) -> dict[str, object]:
    return {
        "detailed_feedback": [dict(_P2_DEEPDIVE_ARGS)],
        "revision_suggestions": _suggestions(suggestion_count),
        "category_score": 6,
    }


class TestSeverityEnumPin:
    """``severity`` is a Literal of the FeedbackSeverity vocabulary."""

    @pytest.mark.parametrize("severity", _ENGLISH_SEVERITIES)
    def test_english_severity_accepted_phase1(self, severity: str) -> None:
        args = {**_P1_FEEDBACK_ARGS, "severity": severity}
        assert AgentFeedbackItem.model_validate(args).severity == severity

    @pytest.mark.parametrize("severity", _ENGLISH_SEVERITIES)
    def test_english_severity_accepted_phase2(self, severity: str) -> None:
        args = {**_P2_DEEPDIVE_ARGS, "severity": severity}
        assert AgentDeepDiveFeedback.model_validate(args).severity == severity

    @pytest.mark.parametrize("severity", _GERMAN_SEVERITIES)
    def test_german_severity_rejected_phase1(self, severity: str) -> None:
        """Regression: the German drift from run 2026-09-14-168945f4-1."""
        args = {**_P1_FEEDBACK_ARGS, "severity": severity}
        with pytest.raises(ValidationError, match="severity"):
            AgentFeedbackItem.model_validate(args)

    @pytest.mark.parametrize("severity", _GERMAN_SEVERITIES)
    def test_german_severity_rejected_phase2(self, severity: str) -> None:
        """Regression: the German drift from run 2026-09-14-168945f4-1."""
        args = {**_P2_DEEPDIVE_ARGS, "severity": severity}
        with pytest.raises(ValidationError, match="severity"):
            AgentDeepDiveFeedback.model_validate(args)

    def test_empty_severity_rejected(self) -> None:
        with pytest.raises(ValidationError, match="severity"):
            AgentDeepDiveFeedback.model_validate({**_P2_DEEPDIVE_ARGS, "severity": ""})


class TestRevisionSuggestionCountContract:
    """``revision_suggestions`` is count-validated to the 3-6 contract."""

    def test_bounds_constants_pin_the_contract(self) -> None:
        assert (MIN_REVISION_SUGGESTIONS, MAX_REVISION_SUGGESTIONS) == (3, 6)

    @pytest.mark.parametrize("count", (3, 6))
    def test_bounds_inclusive_accepted(self, count: int) -> None:
        output = BetaReaderPhase2Output.model_validate(_phase2_args(count))
        assert len(output.revision_suggestions) == count

    @pytest.mark.parametrize("count", (0, 2))
    def test_below_minimum_rejected(self, count: int) -> None:
        with pytest.raises(ValidationError, match="revision_suggestions"):
            BetaReaderPhase2Output.model_validate(_phase2_args(count))

    @pytest.mark.parametrize("count", (7, 8))
    def test_above_maximum_rejected(self, count: int) -> None:
        """8 is the measured violation from run 2026-09-14-168945f4-1."""
        with pytest.raises(ValidationError, match="revision_suggestions"):
            BetaReaderPhase2Output.model_validate(_phase2_args(count))

    def test_error_message_names_the_contract_bounds(self) -> None:
        """The retry message the model sees must state the 3-6 contract."""
        with pytest.raises(ValidationError, match=r"3 to 6 suggestions, got 8"):
            BetaReaderPhase2Output.model_validate(_phase2_args(8))
