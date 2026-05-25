"""Suggestion domain types for proactive context results.

Defines the data structures used by ProactiveContextService:
- EntityMetadata: Lightweight KB entry info passed from the API layer.
- Suggestion: A ranked KB entry returned to the caller.

Both are frozen dataclasses following the pattern in embeddings/store.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class EntityMetadata:
    """Lightweight metadata about a KB entry, provided by the API layer.

    The core service uses this to:
    - Map entity names to entry IDs for name-match boost.
    - Populate usage_count and last_referenced_at for hybrid scoring.
    - Fill entry_type and name in the resulting Suggestion.

    Attributes:
        name: Display name of the entity.
        entity_type: Entity type (character, location, faction, etc.).
        usage_count: How many times this entry has been accepted.
        last_referenced_at: When this entry was last accepted.
    """

    name: str
    entity_type: str
    usage_count: int
    last_referenced_at: datetime | None


@dataclass(frozen=True, slots=True)
class Suggestion:
    """A KB entry suggested as relevant context for a chapter.

    Attributes:
        entry_id: UUID of the suggested KB entry.
        entry_type: Entity type (character, location, faction, etc.).
        name: Display name of the entity.
        relevance_score: Final hybrid score (0.0-1.0).
        reason: Why this entry was suggested.
        similarity: Raw embedding cosine similarity (0.0-1.0).
        usage_count: How many times this entry has been accepted.
        last_referenced_at: When this entry was last accepted.
    """

    entry_id: UUID
    entry_type: str
    name: str
    relevance_score: float
    reason: Literal["mentioned_in_text", "semantically_similar", "recently_used"]
    similarity: float
    usage_count: int
    last_referenced_at: datetime | None
