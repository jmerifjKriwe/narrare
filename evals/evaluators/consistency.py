"""Deterministic evaluators for ADR-044 staged consistency evals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from evals.consistency_models import StagedConsistencyResult


@dataclass
class FactExtractionRecall(Evaluator[Any, StagedConsistencyResult, dict[str, Any]]):
    """Score expected structured facts found in Stage 1 output."""

    def evaluate(
        self, ctx: EvaluatorContext[Any, StagedConsistencyResult, dict[str, Any]]
    ) -> float:
        expected = _expected_fact_keys(ctx.metadata)
        if not expected:
            return 1.0
        actual = _actual_fact_keys(ctx.output)
        matched = sum(1 for fact in expected if fact in actual)
        return matched / len(expected)


@dataclass
class FactExtractionPrecision(Evaluator[Any, StagedConsistencyResult, dict[str, Any]]):
    """Score whether Stage 1 avoids extra facts outside the golden set."""

    def evaluate(
        self, ctx: EvaluatorContext[Any, StagedConsistencyResult, dict[str, Any]]
    ) -> float:
        expected = _expected_fact_keys(ctx.metadata)
        if not expected:
            return 1.0
        actual = _actual_fact_keys(ctx.output)
        if not actual:
            return 0.0
        matched = sum(1 for fact in actual if fact in expected)
        return matched / len(actual)


@dataclass
class ContradictionRecall(Evaluator[Any, StagedConsistencyResult, dict[str, Any]]):
    """Score expected contradiction signatures found in consistency issues."""

    def evaluate(
        self, ctx: EvaluatorContext[Any, StagedConsistencyResult, dict[str, Any]]
    ) -> float:
        expected_groups = _metadata_keyword_groups(ctx.metadata, "expected_issue_keywords")
        if not expected_groups:
            return 1.0
        issue_texts = [_issue_text(issue) for issue in ctx.output.issues]
        matched = sum(1 for group in expected_groups if _group_matches(group, issue_texts))
        return matched / len(expected_groups)


@dataclass
class FalsePositiveGuard(Evaluator[Any, StagedConsistencyResult, dict[str, Any]]):
    """Score 1.0 when known non-contradictions are not reported as issues."""

    def evaluate(
        self, ctx: EvaluatorContext[Any, StagedConsistencyResult, dict[str, Any]]
    ) -> float:
        forbidden_groups = _metadata_keyword_groups(ctx.metadata, "forbidden_issue_keywords")
        if not forbidden_groups:
            return 1.0
        issue_texts = [_issue_text(issue) for issue in ctx.output.issues]
        forbidden_matches = sum(
            1 for group in forbidden_groups if _group_matches(group, issue_texts)
        )
        return 1.0 if forbidden_matches == 0 else 0.0


def _actual_fact_keys(output: StagedConsistencyResult) -> set[tuple[str, str, str]]:
    return {
        _fact_key(
            {
                "subject": fact.subject,
                "predicate": fact.predicate,
                "object_value": fact.object_value,
            }
        )
        for fact in output.extracted_facts
    }


def _expected_fact_keys(metadata: dict[str, Any] | None) -> set[tuple[str, str, str]]:
    expected = _metadata_dicts(metadata, "expected_facts")
    return {_fact_key(item) for item in expected}


def _fact_key(raw: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(raw.get("subject", "")).strip().casefold(),
        str(raw.get("predicate", "")).strip().casefold(),
        str(raw.get("object_value", "")).strip().casefold(),
    )


def _metadata_dicts(metadata: dict[str, Any] | None, key: str) -> list[dict[str, object]]:
    if metadata is None:
        return []
    value: object = metadata.get(key)
    if not isinstance(value, list):
        return []
    result: list[dict[str, object]] = []
    for item in cast("list[object]", value):
        if isinstance(item, dict):
            result.append(cast("dict[str, object]", item))
    return result


def _metadata_keyword_groups(metadata: dict[str, Any] | None, key: str) -> list[list[str]]:
    if metadata is None:
        return []
    value: object = metadata.get(key)
    if not isinstance(value, list):
        return []
    groups: list[list[str]] = []
    for raw_group in cast("list[object]", value):
        if isinstance(raw_group, list):
            group = [item for item in cast("list[object]", raw_group) if isinstance(item, str)]
            if group:
                groups.append(group)
        elif isinstance(raw_group, str):
            groups.append([raw_group])
    return groups


def _issue_text(issue: object) -> str:
    description = str(getattr(issue, "description", ""))
    conflicting = " ".join(str(item) for item in getattr(issue, "conflicting_facts", []))
    locations = " ".join(str(item) for item in getattr(issue, "locations", []))
    return f"{description} {conflicting} {locations}".casefold()


def _group_matches(keywords: list[str], issue_texts: list[str]) -> bool:
    normalized = [keyword.casefold() for keyword in keywords]
    return any(all(keyword in issue_text for keyword in normalized) for issue_text in issue_texts)
