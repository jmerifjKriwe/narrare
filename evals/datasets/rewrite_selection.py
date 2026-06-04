"""Rewrite selection Pydantic Evals dataset."""

from __future__ import annotations

from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance

from evals.evaluators import RewriteModeMatch
from evals.models import RewriteSelectionInput, RewriteSelectionResult


def build_dataset() -> Dataset[RewriteSelectionInput, RewriteSelectionResult, dict[str, Any]]:
    """Build the rewrite selection eval dataset."""

    return Dataset(
        name="rewrite_selection",
        cases=[
            Case(
                name="tone-soften",
                inputs=RewriteSelectionInput(
                    selection_text="You failed us, and everyone knows it.",
                    context_before="The council room fell silent.",
                    context_after="Mara looked away first.",
                    rewrite_mode="tone",
                    instruction="Make the accusation less cruel but still tense.",
                ),
                expected_output=None,
                metadata={"expected_mode": "tone"},
            ),
            Case(
                name="voice-character",
                inputs=RewriteSelectionInput(
                    selection_text="We should leave before sunrise.",
                    context_before="Iven checked the saddle straps.",
                    context_after="The horses stamped in the cold.",
                    rewrite_mode="voice",
                    instruction="Use Captain Iven's clipped soldier voice.",
                ),
                expected_output=None,
                metadata={"expected_mode": "voice"},
            ),
        ],
        evaluators=[IsInstance(type_name="RewriteSelectionResult"), RewriteModeMatch()],
    )
