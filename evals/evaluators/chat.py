"""Deterministic evaluators for chat generation evals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from evals.models import ChatGenerationResult


@dataclass
class ChatGenerationOutputValidator(Evaluator[Any, ChatGenerationResult, dict[str, Any]]):
    """Score 1.0 if the output contains a non-empty text string."""

    def evaluate(self, ctx: EvaluatorContext[Any, ChatGenerationResult, dict[str, Any]]) -> float:
        return 1.0 if ctx.output.text and ctx.output.text.strip() else 0.0


@dataclass
class ChatDraftStructureMatch(Evaluator[Any, ChatGenerationResult, dict[str, Any]]):
    """For draft agent type, verify draft_output has expected structure.

    Checks three fields: non-empty text, word_count > 0, and non-None title.
    Returns 1.0 for non-draft types (not applicable).
    Score = matched_fields / 3 for draft type.
    """

    def evaluate(self, ctx: EvaluatorContext[Any, ChatGenerationResult, dict[str, Any]]) -> float:
        if not ctx.metadata:
            return 1.0
        agent_type = ctx.metadata.get("agent_type")
        if agent_type != "draft":
            return 1.0

        do = ctx.output.draft_output
        if do is None:
            return 0.0

        checks = 0
        if do.text and do.text.strip():
            checks += 1
        if do.word_count > 0:
            checks += 1
        if do.title is not None:
            checks += 1
        return checks / 3
