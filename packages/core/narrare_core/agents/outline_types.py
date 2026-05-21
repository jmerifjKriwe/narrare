"""Output types for OutlineAgent.

Siehe ADR-015 Phase 2.1 — Output Types.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class OutlineOutput(BaseModel):
    """Structured output of an OutlineAgent run.

    Attributes:
        chapter_title: Suggested title for the chapter.
        scenes: List of scene descriptions in order.
        outline_text: Full outline as continuous text.
        metadata: Additional metadata (model info, tokens, etc.)
    """

    chapter_title: str = ""
    scenes: list[str] = []
    outline_text: str = ""
    metadata: dict[str, Any] = {}
