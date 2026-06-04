"""Unit tests for Narrare Pydantic Evals custom evaluators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evals.evaluators import KBExtractionCoverage, PreferenceSignalCoverage, RewriteModeMatch
from evals.models import (
    KBExtractionItem,
    KBExtractionResult,
    PreferenceAnalysisResult,
    RewriteSelectionResult,
)


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
        DummyContext(output=output, metadata={"expected_names": ["Mara", "Iven"]})  # type: ignore[arg-type]
    )

    assert score == 0.5


def test_rewrite_mode_match_rewards_mode_and_text() -> None:
    output = RewriteSelectionResult(selected_mode="tone", rewritten_text="Softer text")

    score = RewriteModeMatch().evaluate(
        DummyContext(output=output, metadata={"expected_mode": "tone"})  # type: ignore[arg-type]
    )

    assert score == 1.0


def test_preference_signal_coverage_scores_all_buckets() -> None:
    output = PreferenceAnalysisResult(
        style_patterns=["prefers concise prose"],
        content_patterns=["prefers dialogue conflict"],
        avoidance_patterns=["avoids exposition"],
        confidence=0.8,
    )

    score = PreferenceSignalCoverage().evaluate(
        DummyContext(
            output=output,
            metadata={
                "style_keywords": ["concise"],
                "content_keywords": ["dialogue"],
                "avoidance_keywords": ["exposition"],
            },
        )  # type: ignore[arg-type]
    )

    assert score == 1.0
