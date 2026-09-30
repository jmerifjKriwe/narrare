"""Unit tests for consistency_triage_types (DecisionModel-pattern pilot, Weg A)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.agents.consistency_triage_types import (
    BAND_TO_CONFIDENCE,
    SEVERITY_TO_CONSISTENCY,
    ConfidenceBand,
    ConsistencyTriageOutput,
    SeverityRubric,
    TriageAssessment,
    TriageEvidence,
    apply_triage,
)
from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyIssue,
    ConsistencyOutput,
    ConsistencySeverity,
)


def _issue(i: int, severity: ConsistencySeverity = ConsistencySeverity.WARNING) -> ConsistencyIssue:
    return ConsistencyIssue(
        check_type=ConsistencyCheckType.PLOT,
        severity=severity,
        description=f"issue {i}",
        locations=["ch1"],
        conflicting_facts=["fact a", "fact b"],
        confidence=0.5,
    )


class TestRubricMappings:
    def test_severity_rubric_covers_all_levels(self) -> None:
        assert SEVERITY_TO_CONSISTENCY[SeverityRubric.NO_ISSUE] == ConsistencySeverity.INFO
        assert SEVERITY_TO_CONSISTENCY[SeverityRubric.MINOR] == ConsistencySeverity.INFO
        assert SEVERITY_TO_CONSISTENCY[SeverityRubric.WARNING] == ConsistencySeverity.WARNING
        assert SEVERITY_TO_CONSISTENCY[SeverityRubric.ERROR] == ConsistencySeverity.ERROR

    def test_band_to_confidence_within_bounds(self) -> None:
        for value in BAND_TO_CONFIDENCE.values():
            assert 0.0 <= value <= 1.0


class TestApplyTriage:
    def test_regrades_severity_and_confidence(self) -> None:
        output = ConsistencyOutput(issues=[_issue(0), _issue(1)])
        triage = ConsistencyTriageOutput(
            assessments=[
                TriageAssessment(
                    issue_index=0,
                    severity=SeverityRubric.ERROR,
                    evidence=TriageEvidence(
                        facts_directly_contradict=True,
                        both_facts_explicitly_stated=True,
                        contradiction_verifiable_without_external_knowledge=True,
                        could_be_intentional_stylistic_choice=False,
                    ),
                    confidence=ConfidenceBand.HIGH,
                ),
                TriageAssessment(
                    issue_index=1,
                    severity=SeverityRubric.WARNING,
                    evidence=TriageEvidence(
                        facts_directly_contradict=True,
                        both_facts_explicitly_stated=False,
                        contradiction_verifiable_without_external_knowledge=True,
                        could_be_intentional_stylistic_choice=True,
                    ),
                    confidence=ConfidenceBand.MEDIUM,
                ),
            ]
        )
        result = apply_triage(output, triage)
        assert result.issues[0].severity == ConsistencySeverity.ERROR
        assert result.issues[0].confidence == BAND_TO_CONFIDENCE[ConfidenceBand.HIGH]
        assert result.issues[1].severity == ConsistencySeverity.WARNING

    def test_no_issue_assessment_drops_issue(self) -> None:
        output = ConsistencyOutput(issues=[_issue(0)])
        triage = ConsistencyTriageOutput(
            assessments=[
                TriageAssessment(
                    issue_index=0,
                    severity=SeverityRubric.NO_ISSUE,
                    evidence=TriageEvidence(
                        facts_directly_contradict=False,
                        both_facts_explicitly_stated=False,
                        contradiction_verifiable_without_external_knowledge=True,
                        could_be_intentional_stylistic_choice=True,
                    ),
                    confidence=ConfidenceBand.HIGH,
                )
            ]
        )
        result = apply_triage(output, triage)
        assert result.issues == []

    def test_index_out_of_range_raises(self) -> None:
        output = ConsistencyOutput(issues=[_issue(0)])
        triage = ConsistencyTriageOutput(
            assessments=[
                TriageAssessment(
                    issue_index=7,
                    severity=SeverityRubric.MINOR,
                    evidence=TriageEvidence(
                        facts_directly_contradict=True,
                        both_facts_explicitly_stated=True,
                        contradiction_verifiable_without_external_knowledge=True,
                        could_be_intentional_stylistic_choice=False,
                    ),
                    confidence=ConfidenceBand.LOW,
                )
            ]
        )
        with pytest.raises(ValueError):
            apply_triage(output, triage)

    def test_negative_issue_index_rejected(self) -> None:
        """Boundary: issue_index is constrained to ge=0 at the model level."""
        with pytest.raises(ValidationError):
            TriageAssessment(
                issue_index=-1,
                severity=SeverityRubric.MINOR,
                evidence=TriageEvidence(
                    facts_directly_contradict=True,
                    both_facts_explicitly_stated=True,
                    contradiction_verifiable_without_external_knowledge=True,
                    could_be_intentional_stylistic_choice=False,
                ),
                confidence=ConfidenceBand.LOW,
            )
