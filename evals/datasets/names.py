"""Name-generation Pydantic Evals dataset (character / place / plot).

Mirrors ``rewrite_selection`` (dataset shape) and the ``writing_prose``
suite (one case per kind, tagged via ``metadata``). The ``names`` suite is
smoke-only — it has no runtime task. Each case ``metadata`` carries the
``name_type`` so the metadata-aware ``NameListQuality`` evaluator and any
future drift follow-up can select per-kind behaviour.
"""

from __future__ import annotations

from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance

from evals.evaluators import NameListQuality
from evals.models import NameGenerationInput, NameGenerationResult


def build_dataset() -> Dataset[NameGenerationInput, NameGenerationResult, dict[str, Any]]:
    """Build the name-generation eval dataset.

    One case per ``name_type`` (character / place / plot). The character
    case supplies ``seed_terms`` so the smoke task's seed-folding path is
    exercised; its evaluator asserts the derived name is not merely echoed.
    """

    return Dataset(
        name="names",
        cases=[
            Case(
                name="character-names-with-seed",
                inputs=NameGenerationInput(
                    name_type="character",
                    count=3,
                    seed_terms=["silver"],
                    constraints="Avoid modern surnames.",
                ),
                expected_output=None,
                metadata={"name_type": "character"},
            ),
            Case(
                name="place-names",
                inputs=NameGenerationInput(
                    name_type="place",
                    count=3,
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"name_type": "place"},
            ),
            Case(
                name="plot-names",
                inputs=NameGenerationInput(
                    name_type="plot",
                    count=3,
                    seed_terms=["crown"],
                ),
                expected_output=None,
                metadata={"name_type": "plot"},
            ),
        ],
        evaluators=[
            IsInstance(type_name="NameGenerationResult"),
            NameListQuality(),
        ],
    )
