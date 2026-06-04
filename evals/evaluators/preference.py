"""Deterministic evaluators for preference analysis evals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from evals.models import PreferenceAnalysisResult


@dataclass
class PreferenceSignalCoverage(Evaluator[Any, PreferenceAnalysisResult, dict[str, Any]]):
    """Score whether expected preference signals are present in output buckets."""

    def evaluate(
        self,
        ctx: EvaluatorContext[Any, PreferenceAnalysisResult, dict[str, Any]],
    ) -> float:
        checks = [
            _bucket_score(ctx.output.style_patterns, ctx.metadata, "style_keywords"),
            _bucket_score(ctx.output.content_patterns, ctx.metadata, "content_keywords"),
            _bucket_score(ctx.output.avoidance_patterns, ctx.metadata, "avoidance_keywords"),
        ]
        expected_checks = [score for score in checks if score is not None]
        if not expected_checks:
            return 1.0
        confidence_bonus = 1.0 if ctx.output.confidence >= 0.5 else ctx.output.confidence
        return (sum(expected_checks) / len(expected_checks) * 0.85) + (confidence_bonus * 0.15)


def _bucket_score(
    actual_patterns: list[str],
    metadata: dict[str, Any] | None,
    key: str,
) -> float | None:
    if metadata is None:
        return None
    raw_keywords: object = metadata.get(key)
    if not isinstance(raw_keywords, list):
        return None
    keyword_items = cast("list[object]", raw_keywords)
    keywords = [item.casefold() for item in keyword_items if isinstance(item, str)]
    if not keywords:
        return None
    actual_text = "\n".join(actual_patterns).casefold()
    return sum(1 for keyword in keywords if keyword in actual_text) / len(keywords)
