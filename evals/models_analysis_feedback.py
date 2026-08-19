"""Eval models for the analysis_feedback suite.

Extracted from ``evals/models.py`` per RULE-04 (modularize, do not compress)
to mirror ``models_writing.py`` / ``models_planning.py`` /
``models_kb_operations.py``. The models are re-exported from
``evals.models`` so existing ``from evals.models import ...`` imports keep
working.

The analysis_feedback suite evaluates the long-form feedback agents
(``beta_reader``, ``review``, ``consistency``): the graded output is a
normalized pass/fail verdict with issue count, quality score, and summary
(consumed by the ``AnalysisFeedbackQuality`` evaluator).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

__all__ = [
    "AnalysisFeedbackInput",
    "AnalysisFeedbackResult",
]


class AnalysisFeedbackInput(BaseModel):
    """Input for analysis/feedback agent eval cases."""

    agent_type: Literal["beta_reader", "review", "consistency"]
    text_content: str
    genre: str = "Fantasy"
    language: str = "en"


class AnalysisFeedbackResult(BaseModel):
    """Normalized analysis/feedback result."""

    passed: bool = False
    issues_found: int = 0
    quality_score: int = 0
    summary: str = ""
