"""Context assembly input models for the writing subsystem.

Extracted from ``models.py`` for RULE-04 compliance (max 200 lines).

These dataclasses represent the inputs passed from the API layer to the
context assembler.  The API layer is responsible for computing similarity,
frequency, and recency scores before passing entities to the assembler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

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
    metadata: dict[str, Any] | None = None  # structured entity metadata (speech, personality)

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


@dataclass(slots=True)
class ContextMetadata:
    """Lightweight summary of assembled writing context for client display.

    This is sent to the frontend as the first SSE event before text streaming
    begins.  It gives authors visibility into what context was assembled for
    the LLM — addressing the "black box" feeling identified in CR-07.
    """

    # Tier counts
    kb_characters_count: int = 0
    kb_locations_count: int = 0
    kb_factions_count: int = 0
    kb_suggested_count: int = 0
    kb_pinned_count: int = 0
    recent_chapter_count: int = 0

    # Entity names (for display in Context Inspector UI)
    character_names: list[str] = field(default_factory=lambda: [])
    location_names: list[str] = field(default_factory=lambda: [])
    faction_names: list[str] = field(default_factory=lambda: [])

    # Flags
    is_first_chapter: bool = False
    has_user_preferences: bool = False
    tone: str = "balanced"

    # Token budget info
    total_budget_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for SSE transmission."""
        return {
            "kb_characters_count": self.kb_characters_count,
            "kb_locations_count": self.kb_locations_count,
            "kb_factions_count": self.kb_factions_count,
            "kb_suggested_count": self.kb_suggested_count,
            "kb_pinned_count": self.kb_pinned_count,
            "recent_chapter_count": self.recent_chapter_count,
            "character_names": self.character_names,
            "location_names": self.location_names,
            "faction_names": self.faction_names,
            "is_first_chapter": self.is_first_chapter,
            "has_user_preferences": self.has_user_preferences,
            "tone": self.tone,
            "total_budget_tokens": self.total_budget_tokens,
        }
