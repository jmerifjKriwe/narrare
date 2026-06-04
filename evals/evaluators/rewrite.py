"""Deterministic evaluators for rewrite selection evals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from evals.models import RewriteSelectionResult


@dataclass
class RewriteModeMatch(Evaluator[Any, RewriteSelectionResult, dict[str, Any]]):
    """Score whether the rewrite task selected the expected rewrite mode."""

    def evaluate(self, ctx: EvaluatorContext[Any, RewriteSelectionResult, dict[str, Any]]) -> float:
        if ctx.metadata is None:
            return 0.0
        expected_mode = ctx.metadata.get("expected_mode")
        if not isinstance(expected_mode, str):
            return 0.0
        mode_score = 1.0 if ctx.output.selected_mode == expected_mode else 0.0
        text_score = 1.0 if ctx.output.rewritten_text.strip() else 0.0
        return (mode_score * 0.8) + (text_score * 0.2)
