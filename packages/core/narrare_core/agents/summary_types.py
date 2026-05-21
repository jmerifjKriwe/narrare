"""Output types for ChapterSummaryAgent.

See ADR-015 Phase 2.1 — Output Types.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SummaryOutput(BaseModel):
    """Structured output of a ChapterSummaryAgent run.

    Attributes:
        summary: The generated summary text (2-4 sentences).
        key_points: Key narrative points extracted from the chapter.
        word_count: Word count of the summary itself.
        metadata: Additional metadata (model info, tokens, etc.).
    """

    summary: str = ""
    key_points: list[str] = []
    word_count: int = 0
    metadata: dict[str, Any] = {}
