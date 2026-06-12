"""Deterministic evaluators for analysis/feedback evals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from evals.models import AnalysisFeedbackResult


@dataclass
class AnalysisFeedbackValidator(Evaluator[Any, AnalysisFeedbackResult, dict[str, Any]]):
    """Validate structural properties of the analysis feedback result.

    Checks:
    - issues_found >= 0
    - quality_score between 1 and 10
    Score = matched_checks / 2
    """

    def evaluate(self, ctx: EvaluatorContext[Any, AnalysisFeedbackResult, dict[str, Any]]) -> float:
        checks = 0
        if ctx.output.issues_found >= 0:
            checks += 1
        if 1 <= ctx.output.quality_score <= 10:
            checks += 1
        return checks / 2


@dataclass
class AnalysisFeedbackContent(Evaluator[Any, AnalysisFeedbackResult, dict[str, Any]]):
    """Score 1.0 if the summary is a non-empty string."""

    def evaluate(self, ctx: EvaluatorContext[Any, AnalysisFeedbackResult, dict[str, Any]]) -> float:
        return 1.0 if ctx.output.summary and ctx.output.summary.strip() else 0.0
