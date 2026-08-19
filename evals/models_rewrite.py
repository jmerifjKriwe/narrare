"""Eval models for the rewrite_selection suite.

Extracted from ``evals/models.py`` per RULE-04 (modularize, do not compress)
to mirror ``models_writing.py`` / ``models_planning.py`` /
``models_kb_operations.py``. The models are re-exported from
``evals.models`` so existing ``from evals.models import ...`` imports keep
working.

The rewrite_selection suite evaluates mode selection for inline rewrite:
given a selection with surrounding context, an instruction, and a candidate
``rewrite_mode``, the graded output is the selected mode plus the rewritten
text (consumed by the ``RewriteModeCorrectness`` evaluator).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

__all__ = [
    "RewriteSelectionInput",
    "RewriteSelectionResult",
]


class RewriteSelectionInput(BaseModel):
    """Input for rewrite selection eval cases."""

    selection_text: str
    context_before: str = ""
    context_after: str = ""
    rewrite_mode: Literal["tone", "style", "voice", "fix", "custom"]
    instruction: str
    genre: str = "Fantasy"


class RewriteSelectionResult(BaseModel):
    """Structured rewrite selection result."""

    selected_mode: str
    rewritten_text: str
    rationale: str = ""
