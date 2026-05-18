"""Context assembly input models for the writing subsystem.

Extracted from ``models.py`` for RULE-04 compliance (max 200 lines).

These dataclasses represent the inputs passed from the API layer to the
context assembler.  The API layer is responsible for computing similarity,
frequency, and recency scores before passing entities to the assembler.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(slots=True)
class KBEntity:
    """A KB entity passed from the API layer to the context assembler.

    The API layer is responsible for computing similarity, frequency,
    and recency scores before passing entities to the assembler.
    """

    entity_id: str
    entity_type: str  # "character", "location", "faction"
    name: str
    content: str
    similarity_score: float = 0.0
    frequency_score: float = 0.0
    recency_score: float = 0.0
    is_referenced: bool = False
    is_pinned: bool = False

    @property
    def relevance_score(self) -> float:
        """Weighted relevance: 50 % similarity + 30 % frequency + 20 % recency."""
        return (
            0.50 * self.similarity_score + 0.30 * self.frequency_score + 0.20 * self.recency_score
        )


@dataclass(slots=True)
class RecentChapter:
    """A recent chapter provided by the API layer to the context assembler.

    The API layer provides both full text and a pre-computed summary.
    The assembler decides which to use based on token budget.
    """

    chapter_id: UUID
    title: str
    full_text: str
    summary: str  # Pre-computed by API layer (using SUMMARIZE intent)
    position: int  # Chapter position (higher = more recent)
