"""Agent-level tests for ConsistencyTriageAgent (TestModel, no LLM).

Covers:
- happy path: one assessment per issue (exact index sequence),
- prompt serialization of the issues under review,
- ADR-035 output validator: missing / duplicate / out-of-order assessments
  trigger ModelRetry → ModelRetryExhaustedError at the NarrareAgent boundary.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models.test import TestModel

from narrare_core.agents.consistency_triage_agent import (
    ConsistencyTriageAgent,
    build_triage_prompt,
)
from narrare_core.agents.consistency_triage_types import (
    ConfidenceBand,
    ConsistencyTriageDeps,
    SeverityRubric,
)
from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyIssue,
    ConsistencySeverity,
)
from narrare_core.agents.errors import ModelRetryExhaustedError


def _issue(i: int = 0) -> ConsistencyIssue:
    return ConsistencyIssue(
        check_type=ConsistencyCheckType.CHARACTER,
        severity=ConsistencySeverity.WARNING,
        description=(
            f"Issue {i}: Anna is described as an only child in ch1 but has a brother in ch3."
        ),
        locations=["ch1", "ch3"],
        conflicting_facts=["Anna is an only child", "Anna's brother Tomas"],
        confidence=0.5,
    )


def _deps(n_issues: int = 1) -> ConsistencyTriageDeps:
    return ConsistencyTriageDeps(language="en", issues=[_issue(i) for i in range(n_issues)])


def _assessment_args(index: int) -> dict[str, Any]:
    """Tool-call args for one valid TriageAssessment (TestModel format)."""
    return {
        "issue_index": index,
        "severity": SeverityRubric.WARNING,
        "evidence": {
            "facts_directly_contradict": True,
            "both_facts_explicitly_stated": True,
            "contradiction_verifiable_without_external_knowledge": True,
            "could_be_intentional_stylistic_choice": False,
        },
        "confidence": ConfidenceBand.MEDIUM,
    }


async def test_run_with_test_model_returns_assessment_per_issue() -> None:
    """Valid args pass the validator (``assessments`` defaults to ``[]``, so
    TestModel cannot auto-fill the list — POV-agent custom_output_args idiom)."""
    agent = ConsistencyTriageAgent(
        model=TestModel(custom_output_args={"assessments": [_assessment_args(0)]})
    )
    result = await agent.run(prompt=build_triage_prompt(_deps()), deps=_deps())
    # Exact sequence (count, order, uniqueness) — assessments apply positionally.
    assert [a.issue_index for a in result.assessments] == [0]


def test_build_triage_prompt_contains_issue_facts_and_indices() -> None:
    prompt = build_triage_prompt(_deps())
    assert "Anna is an only child" in prompt
    assert "Anna's brother Tomas" in prompt
    assert "[0]" in prompt  # index marker


async def test_run_with_missing_assessment_raises_retry_exhausted() -> None:
    """ADR-035: empty assessments violate one-per-issue → ModelRetry →
    retries exhausted → ModelRetryExhaustedError (NarrareAgent boundary)."""
    agent = ConsistencyTriageAgent(model=TestModel(custom_output_args={"assessments": []}))
    with pytest.raises(ModelRetryExhaustedError) as exc_info:
        await agent.run(prompt="Triage.", deps=_deps())
    assert isinstance(exc_info.value.original, UnexpectedModelBehavior)


async def test_run_with_duplicate_issue_index_raises_retry_exhausted() -> None:
    """Duplicate indices would silently re-apply one assessment — rejected."""
    agent = ConsistencyTriageAgent(
        model=TestModel(
            custom_output_args={"assessments": [_assessment_args(0), _assessment_args(0)]}
        )
    )
    with pytest.raises(ModelRetryExhaustedError):
        await agent.run(prompt="Triage.", deps=_deps(n_issues=2))


async def test_run_with_out_of_order_indices_raises_retry_exhausted() -> None:
    """Out-of-order indices would positional-apply the wrong rubric — rejected."""
    agent = ConsistencyTriageAgent(
        model=TestModel(
            custom_output_args={"assessments": [_assessment_args(1), _assessment_args(0)]}
        )
    )
    with pytest.raises(ModelRetryExhaustedError):
        await agent.run(prompt="Triage.", deps=_deps(n_issues=2))
