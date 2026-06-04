"""Deterministic evaluators for KB extraction evals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from evals.models import KBExtractionResult


@dataclass
class KBExtractionCoverage(Evaluator[Any, KBExtractionResult, dict[str, Any]]):
    """Score whether required KB entities or relations are extracted."""

    def evaluate(self, ctx: EvaluatorContext[Any, KBExtractionResult, dict[str, Any]]) -> float:
        expected_names = _metadata_list(ctx.metadata, "expected_names")
        if not expected_names:
            return 1.0
        output_names = {item.name.casefold() for item in ctx.output.results}
        matched = sum(1 for name in expected_names if name.casefold() in output_names)
        return matched / len(expected_names)


def _metadata_list(metadata: dict[str, Any] | None, key: str) -> list[str]:
    if metadata is None:
        return []
    value: object = metadata.get(key)
    if not isinstance(value, list):
        return []
    items = cast("list[object]", value)
    return [item for item in items if isinstance(item, str)]
