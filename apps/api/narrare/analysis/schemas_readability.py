"""ANAL-003 Readability analysis request schema.

Split from schemas.py for RULE-04 compliance (< 200 lines).
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003 — Pydantic needs UUID at runtime for validation

from pydantic import BaseModel, Field


class ReadabilityRequest(BaseModel):
    """Request for readability analysis.

    Attributes:
        chapter_ids: One or more chapter UUIDs to analyze (1-5).
        language: Language for analysis output. Defaults to ``"en"``.
    """

    chapter_ids: list[UUID] = Field(min_length=1, max_length=5)
    language: str = Field(default="en", min_length=2, max_length=5)
