"""Unit tests for Narrare Pydantic Evals custom evaluators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from evals.consistency_models import StagedConsistencyResult
from evals.evaluators import (
    ContradictionRecall,
    FactExtractionPrecision,
    FactExtractionRecall,
    FalsePositiveGuard,
    KBExtractionCoverage,
    PreferenceSignalCoverage,
    RewriteModeMatch,
)
from evals.models import (
    KBExtractionItem,
    KBExtractionResult,
    PreferenceAnalysisResult,
    RewriteSelectionResult,
)

from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyIssue,
    ConsistencySeverity,
)
from narrare_core.agents.fact_extractor_types import ExtractedFact

if TYPE_CHECKING:
    from pydantic_evals.evaluators import EvaluatorContext


@dataclass(frozen=True)
class DummyContext:
    """Small evaluator context double with only fields our evaluators read."""

    output: Any
    metadata: dict[str, Any] | None = None


def test_kb_extraction_coverage_scores_expected_names() -> None:
    output = KBExtractionResult(
        results=[KBExtractionItem(item_type="new_entity", name="Mara", confidence=0.9)]
    )

    score = KBExtractionCoverage().evaluate(
        _ctx(output=output, metadata={"expected_names": ["Mara", "Iven"]})
    )

    assert score == 0.5


def test_rewrite_mode_match_rewards_mode_and_text() -> None:
    output = RewriteSelectionResult(selected_mode="tone", rewritten_text="Softer text")

    score = RewriteModeMatch().evaluate(_ctx(output=output, metadata={"expected_mode": "tone"}))

    assert score == 1.0


def test_preference_signal_coverage_scores_all_buckets() -> None:
    output = PreferenceAnalysisResult(
        style_patterns=["prefers concise prose"],
        content_patterns=["prefers dialogue conflict"],
        avoidance_patterns=["avoids exposition"],
        confidence=0.8,
    )

    score = PreferenceSignalCoverage().evaluate(
        _ctx(
            output=output,
            metadata={
                "style_keywords": ["concise"],
                "content_keywords": ["dialogue"],
                "avoidance_keywords": ["exposition"],
            },
        )
    )

    assert score == 1.0


def test_fact_extraction_recall_and_precision_score_structured_facts() -> None:
    output = StagedConsistencyResult(
        extracted_facts=[
            _fact("Liora", "left", "Stonebridge at dawn on First Thaw"),
            _fact("Liora", "carried", "brass compass"),
        ]
    )
    metadata = {
        "expected_facts": [
            {
                "subject": "Liora",
                "predicate": "left",
                "object_value": "Stonebridge at dawn on First Thaw",
            },
            {"subject": "Liora", "predicate": "carried", "object_value": "brass compass"},
        ]
    }
    ctx = cast(
        "EvaluatorContext[object, StagedConsistencyResult, dict[str, Any]]",
        DummyContext(output=output, metadata=metadata),
    )

    assert FactExtractionRecall().evaluate(ctx) == 1.0
    assert FactExtractionPrecision().evaluate(ctx) == 1.0


def test_contradiction_recall_matches_issue_keyword_group() -> None:
    output = StagedConsistencyResult(
        issues=[
            _issue(
                "Dax cannot travel from Harbor Market to the Observatory by sunrise.",
                ["Dax at Harbor Market", "Dax at Observatory"],
            )
        ]
    )
    ctx = cast(
        "EvaluatorContext[object, StagedConsistencyResult, dict[str, Any]]",
        DummyContext(
            output=output,
            metadata={"expected_issue_keywords": [["Dax", "Harbor Market", "Observatory"]]},
        ),
    )

    assert ContradictionRecall().evaluate(ctx) == 1.0


def test_false_positive_guard_rejects_forbidden_non_contradiction() -> None:
    output = StagedConsistencyResult(
        issues=[_issue("The cloak changes from black to gray.", ["black cloak", "gray fog"])]
    )
    ctx = cast(
        "EvaluatorContext[object, StagedConsistencyResult, dict[str, Any]]",
        DummyContext(
            output=output, metadata={"forbidden_issue_keywords": [["cloak", "black", "gray"]]}
        ),
    )

    assert FalsePositiveGuard().evaluate(ctx) == 0.0


def _fact(subject: str, predicate: str, object_value: str) -> ExtractedFact:
    return ExtractedFact(
        fact_type="event",
        subject=subject,
        predicate=predicate,
        object_value=object_value,
        chapter_id="ch1",
        evidence_text=f"{subject} {predicate} {object_value}",
        confidence=0.95,
    )


def _ctx(
    *,
    output: object,
    metadata: dict[str, Any] | None = None,
) -> EvaluatorContext[object, Any, dict[str, Any]]:
    return cast(
        "EvaluatorContext[object, Any, dict[str, Any]]",
        DummyContext(output=output, metadata=metadata),
    )


def _issue(description: str, conflicting_facts: list[str]) -> ConsistencyIssue:
    return ConsistencyIssue(
        check_type=ConsistencyCheckType.TIMELINE,
        severity=ConsistencySeverity.ERROR,
        description=description,
        locations=["ch1", "ch2"],
        conflicting_facts=conflicting_facts,
        confidence=0.95,
    )
