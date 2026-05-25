"""KB creation session models.

Pydantic models for the assisted creation session lifecycle.
Sessions are ephemeral (Redis-backed with 30min TTL), not persisted in PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID  # noqa: TC003 — needed at runtime for Pydantic model resolution

from pydantic import BaseModel, Field


class KBCreationField(BaseModel):
    """A single field in an assisted creation session.

    Tracks both user input and AI suggestions with source provenance.
    """

    field_key: str
    label: str
    field_type: Literal["text", "list", "boolean", "select"] = "text"
    required: bool = False
    options: list[str] | None = None  # for select type
    user_value: str | None = None
    ai_suggested_value: str | None = None
    ai_reasoning: str | None = None
    source: Literal["user", "ai", "world_derived", "merged"] = "user"
    final_value: str | None = None


class KBCreationSession(BaseModel):
    """An assisted KB entry creation session.

    Tracks the state of a template-guided creation flow from
    initial entity type selection through completion.
    """

    id: UUID
    novel_id: UUID
    user_id: UUID
    entity_type: str
    status: Literal["active", "review", "complete", "abandoned"] = "active"
    fields: list[KBCreationField] = Field(default_factory=list[KBCreationField])
    context_entries: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
