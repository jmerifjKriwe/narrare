"""Deterministic evaluator for the ``names`` eval suite.

Provider-free and deterministic. The smoke task always produces compliant
output (exactly ``count`` unique, non-empty, stripped names that never
merely echo a seed term verbatim), so ``NameListQuality`` scores ``1.0``
in smoke mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from evals.models_names import NameGenerationInput, NameGenerationResult


@dataclass
class NameListQuality(Evaluator[NameGenerationInput, NameGenerationResult, dict[str, Any]]):
    """Weighted name-list quality score (deterministic, smoke yields 1.0).

    Weighting:
      * 0.3 — (a) ``len(names)`` matches ``inputs.count`` (or ``>= 1`` when
        no count is requested).
      * 0.3 — (b) every name is non-empty and free of surrounding whitespace.
      * 0.2 — (c) no duplicate names (case-insensitive).
      * 0.2 — (d) no name merely echoes a ``seed_terms`` entry verbatim.
    """

    def evaluate(
        self, ctx: EvaluatorContext[NameGenerationInput, NameGenerationResult, dict[str, Any]]
    ) -> float:
        names = ctx.output.names
        inputs = ctx.inputs

        count = inputs.count
        if count and count > 0:
            count_score = 1.0 if len(names) == count else (0.5 if len(names) >= 1 else 0.0)
        else:
            count_score = 1.0 if len(names) >= 1 else 0.0

        nonempty_score = (
            1.0 if names and all(name.strip() and name == name.strip() for name in names) else 0.0
        )

        normalized = [name.strip().casefold() for name in names]
        unique_score = 1.0 if names and len(set(normalized)) == len(normalized) else 0.0

        echoed = {term.strip().casefold() for term in inputs.seed_terms if term.strip()}
        noecho_score = 1.0 if not any(name in echoed for name in normalized) else 0.0

        return (
            (count_score * 0.3)
            + (nonempty_score * 0.3)
            + (unique_score * 0.2)
            + (noecho_score * 0.2)
        )
