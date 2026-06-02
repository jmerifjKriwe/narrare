"""Output types for TemporalExtractionAgent.

See ADR-015 Phase 2.1 — Output Types.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ExtractedTemporalExpression(BaseModel):
    """A single temporal expression extracted from chapter content.

    Attributes:
        expression: Original text (e.g., "three days later").
        event_name: Inferred event name (e.g., "Arrival at the castle").
        timestamp_raw: Raw temporal expression as found in text.
        chapter_reference: Chapter where the expression was found.
        character_names: Characters mentioned near the expression.
        location_name: Location mentioned near the expression.
        confidence: Extraction confidence (0.0-1.0).
        context: Surrounding sentence for user review.
    """

    expression: str = ""
    event_name: str = ""
    timestamp_raw: str = ""
    chapter_reference: str = ""
    character_names: list[str] = []
    location_name: str = ""
    confidence: float = 0.0
    context: str = ""


class TemporalExtractionOutput(BaseModel):
    """Structured output of a TemporalExtractionAgent run.

    Attributes:
        extracted: List of temporal expressions found in the text.
        chapter_temporal_markers: All temporal markers found (for reference).
        extraction_notes: AI notes on extraction quality and confidence.
        metadata: Additional metadata (model info, tokens, etc.).
    """

    extracted: list[ExtractedTemporalExpression] = []
    chapter_temporal_markers: list[str] = []
    extraction_notes: str = ""
    metadata: dict[str, Any] = {}
