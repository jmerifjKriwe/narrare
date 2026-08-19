"""Eval models for the kb_extraction suite.

Extracted from ``evals/models.py`` per RULE-04 (modularize, do not compress)
to mirror ``models_writing.py`` / ``models_planning.py`` /
``models_kb_operations.py``. The models are re-exported from
``evals.models`` so existing ``from evals.models import ...`` imports keep
working.

The kb_extraction suite evaluates the chapter-to-KB extraction pipeline:
``KBExtractionInput`` carries the chapter plus the names of entities that
already exist in the KB (so the extractor can be graded on new-vs-update
discrimination), and ``KBExtractionResult`` normalizes the extraction into
typed items (``new_entity`` / ``update_entity`` / ``relationship`` /
``conflict``) consumed by the ``KBExtractionCorrectness`` evaluator.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

__all__ = [
    "KBExtractionInput",
    "KBExtractionItem",
    "KBExtractionResult",
]


class KBExtractionInput(BaseModel):
    """Input for KB extraction eval cases."""

    chapter_title: str
    genre: str
    chapter_text: str
    existing_entity_names: list[str] = Field(default_factory=list)


class KBExtractionItem(BaseModel):
    """Normalized KB extraction result used by evals."""

    item_type: Literal["new_entity", "update_entity", "relationship", "conflict"]
    name: str
    entity_type: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source_text: str = ""


def _empty_kb_items() -> list[KBExtractionItem]:
    """Return a typed empty extraction item list."""

    return []


class KBExtractionResult(BaseModel):
    """Normalized KB extraction output."""

    results: list[KBExtractionItem] = Field(default_factory=_empty_kb_items)
    analysis_notes: str = ""
