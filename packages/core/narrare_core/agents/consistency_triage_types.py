"""DecisionModel-pattern output types for consistency triage (Weg A pilot).

Adopts pydantic-ai DecisionModel OUTPUT-DESIGN patterns only — IntEnum
rubrics with described levels, BoolCriteria-style evidence booleans,
per-field questions via Field descriptions, and band-style confidence.
NO TypeSafe/Jev integration and NO logprob calibration (Weg B is a
future ADR).

The triage re-scores ConsistencyAgent issues on a CHEAP model
(LLMIntent.CONSISTENCY_TRIAGE, fast tier).
"""

from __future__ import annotations

from enum import IntEnum
from typing import ClassVar

from pydantic import BaseModel, Field

from narrare_core.agents.consistency_types import (
    ConsistencyIssue,
    ConsistencyOutput,
    ConsistencySeverity,
)

_SEVERITY_LEVELS = (
    "0 = NO_ISSUE: facts are consistent or the difference is an intentional "
    "stylistic choice. 1 = MINOR: trivial discrepancy a reader would not "
    "notice. 2 = WARNING: noticeable inconsistency that breaks immersion. "
    "3 = ERROR: impossible contradiction; the plot cannot hold as written."
)
_CONFIDENCE_LEVELS = (
    "0 = LOW: plausible but weakly supported. 1 = MEDIUM: supported by the "
    "quoted facts. 2 = HIGH: the contradiction is explicit in the quoted facts."
)


class SeverityRubric(IntEnum):
    """Described severity levels (level prose in every schema via Field description)."""

    NO_ISSUE = 0
    MINOR = 1
    WARNING = 2
    ERROR = 3


class ConfidenceBand(IntEnum):
    """Banded confidence — deliberately NOT a free-floating 0.0-1.0 self-report."""

    LOW = 0
    MEDIUM = 1
    HIGH = 2


SEVERITY_TO_CONSISTENCY: dict[SeverityRubric, ConsistencySeverity] = {
    SeverityRubric.NO_ISSUE: ConsistencySeverity.INFO,
    SeverityRubric.MINOR: ConsistencySeverity.INFO,
    SeverityRubric.WARNING: ConsistencySeverity.WARNING,
    SeverityRubric.ERROR: ConsistencySeverity.ERROR,
}


class _ConfidenceScale:
    """Fixed band→confidence scale — a rubric constant, not a tunable default.

    Held as ClassVar per RULE-18 (pyright forbids module-level ClassVar, so
    the table lives in a class and is re-exported at module level below,
    keeping the brief-mandated module-level name for Task 11/12 imports).
    """

    BAND_TO_CONFIDENCE: ClassVar[dict[ConfidenceBand, float]] = {
        ConfidenceBand.LOW: 0.3,
        ConfidenceBand.MEDIUM: 0.6,
        ConfidenceBand.HIGH: 0.9,
    }


BAND_TO_CONFIDENCE: dict[ConfidenceBand, float] = _ConfidenceScale.BAND_TO_CONFIDENCE


class TriageEvidence(BaseModel):
    """BoolCriteria pattern — yes/no questions, one boolean each."""

    facts_directly_contradict: bool = Field(
        description="Do the quoted conflicting facts state mutually exclusive things?"
    )
    both_facts_explicitly_stated: bool = Field(
        description="Are BOTH facts explicitly written in the text (not inferred)?"
    )
    contradiction_verifiable_without_external_knowledge: bool = Field(
        description="Can a reader detect the contradiction from the novel alone?"
    )
    could_be_intentional_stylistic_choice: bool = Field(
        description="Could the difference plausibly be an intentional authorial choice?"
    )


class TriageAssessment(BaseModel):
    """Per-field question set for ONE issue (indexed by position in the input list)."""

    issue_index: int = Field(ge=0, description="0-based index into the triaged issue list")
    severity: SeverityRubric = Field(description=_SEVERITY_LEVELS)
    evidence: TriageEvidence
    confidence: ConfidenceBand = Field(description=_CONFIDENCE_LEVELS)


class ConsistencyTriageOutput(BaseModel):
    """Structured triage result — one assessment per input issue."""

    # Mirrors ConsistencyOutput.issues (list of a custom BaseModel) — ``= []``
    # keeps pyright strict happy (Field(default_factory=list) would surface as
    # list[Unknown] for a custom-element list).
    assessments: list[TriageAssessment] = []


def apply_triage(output: ConsistencyOutput, triage: ConsistencyTriageOutput) -> ConsistencyOutput:
    """Fold triage assessments back into a ConsistencyOutput (pure function).

    Rules:
    - NO_ISSUE assessments DROP the issue (false-positive suppression).
    - severity is re-mapped via SEVERITY_TO_CONSISTENCY.
    - confidence is re-mapped via BAND_TO_CONFIDENCE (band, not self-report).
    - assessments with an out-of-range issue_index raise ValueError (ADR-035
      deterministic invariant — caller-side validation retries at the agent
      boundary instead).
    """

    def _update(issue: ConsistencyIssue, assessment: TriageAssessment) -> ConsistencyIssue:
        return issue.model_copy(
            update={
                "severity": SEVERITY_TO_CONSISTENCY[assessment.severity],
                "confidence": BAND_TO_CONFIDENCE[assessment.confidence],
            }
        )

    for assessment in triage.assessments:
        if assessment.issue_index >= len(output.issues):
            raise ValueError(
                f"triage assessment index {assessment.issue_index} out of range "
                f"for {len(output.issues)} issues"
            )

    kept = [
        _update(issue, triage.assessments[i])
        for i, issue in enumerate(output.issues)
        if triage.assessments[i].severity is not SeverityRubric.NO_ISSUE
    ]
    return output.model_copy(update={"issues": kept})


class ConsistencyTriageDeps:
    """Deps for ConsistencyTriageAgent (plain class, ConsistencyDeps pattern)."""

    def __init__(self, language: str = "en", issues: list[ConsistencyIssue] | None = None) -> None:
        self.language = language
        self.issues = issues or []
