"""Output types for ReviewAgent.

Siehe ADR-015 Phase 2.1 — Output Types.
"""

from __future__ import annotations

from pydantic import BaseModel


class ReviewOutput(BaseModel):
    """Structured output of a ReviewAgent run.

    Attributes:
        approved: Whether the draft passes review (true/false).
        feedback: Overall feedback text for the writer.
        suggestions: List of specific improvement suggestions.
        quality_score: 1-10 quality rating.
        issues: List of identified issues (plot holes, pacing, etc.).
    """

    approved: bool = False
    feedback: str = ""
    suggestions: list[str] = []
    quality_score: int = 5
    issues: list[str] = []
