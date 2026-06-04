"""KB extraction Pydantic Evals dataset."""

from __future__ import annotations

from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance

from evals.evaluators import KBExtractionCoverage
from evals.models import KBExtractionInput, KBExtractionResult


def build_dataset() -> Dataset[KBExtractionInput, KBExtractionResult, dict[str, Any]]:
    """Build the KB extraction eval dataset."""

    return Dataset(
        name="kb_extraction",
        cases=[
            Case(
                name="new-character-and-location",
                inputs=KBExtractionInput(
                    chapter_title="The Gate",
                    genre="Fantasy",
                    chapter_text=(
                        "Mara crossed the Moon Gate beneath the ruined city of Solenne. "
                        "Her silver oathmark burned when Captain Iven raised his lantern."
                    ),
                ),
                expected_output=None,
                metadata={"expected_names": ["Mara", "Moon Gate", "Captain Iven"]},
            ),
            Case(
                name="relationship-update",
                inputs=KBExtractionInput(
                    chapter_title="Old Debts",
                    genre="Mystery",
                    chapter_text=(
                        "Detective Noor admitted that Vellum House funded the Ardent Circle. "
                        "Jonas kept the receipt hidden inside the blue ledger."
                    ),
                    existing_entity_names=["Vellum House", "Ardent Circle"],
                ),
                expected_output=None,
                metadata={"expected_names": ["Vellum House", "Ardent Circle", "Jonas"]},
            ),
        ],
        evaluators=[IsInstance(type_name="KBExtractionResult"), KBExtractionCoverage()],
    )
