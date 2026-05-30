"""Pure Pydantic schemas for Free-Form Chat — no FastAPI, no SQLAlchemy.

These are the shared data models used across core and backend layers.
Backend schemas.py may extend these with FastAPI-specific fields.
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003 — needed at runtime for Pydantic model resolution

from pydantic import BaseModel, Field


class ChatMessageSchema(BaseModel):
    """A single chat message."""

    conversation_id: UUID
    role: str = Field(pattern="^(user|assistant)$")
    content: str
    created_at: str = ""


class ChatRequestSchema(BaseModel):
    """Request to send a chat message."""

    project_id: UUID
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None


class ChatResponseSchema(BaseModel):
    """Response metadata for a chat request (before streaming begins)."""

    conversation_id: UUID
    message_id: UUID


class ChatHistoryResponseSchema(BaseModel):
    """Full conversation history response."""

    conversation_id: UUID
    messages: list[ChatMessageSchema]
    created_at: str = ""
    updated_at: str = ""
