"""FastAPI-specific Pydantic schemas for the chat feature.

Extends the core schemas (narrare_core.chat.schemas) with API-specific
request/response models for route validation and OpenAPI documentation.
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003 — needed at runtime for Pydantic model resolution

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Request to send a chat message.

    Extends the core ``ChatRequestSchema`` with FastAPI-specific validation.
    """

    project_id: UUID
    message: str = Field(
        min_length=1,
        max_length=4000,
        description="The user's chat message (1-4000 characters).",
    )
    conversation_id: UUID | None = Field(
        default=None,
        description="Existing conversation ID. Omit to start a new conversation.",
    )


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------


class ChatMessageSchema(BaseModel):
    """A single chat message in API responses."""

    message_id: UUID
    role: str = Field(pattern="^(user|assistant)$")
    content: str
    created_at: str = ""


class ChatHistoryResponse(BaseModel):
    """Full conversation history returned by the API."""

    conversation_id: UUID
    project_id: UUID
    messages: list[ChatMessageSchema]
    created_at: str = ""
    updated_at: str = ""


class ChatDeleteResponse(BaseModel):
    """Confirmation response after clearing conversation history."""

    conversation_id: UUID
    deleted: bool = True


# ---------------------------------------------------------------------------
# SSE Event Schemas
# ---------------------------------------------------------------------------


class ChatMetaEvent(BaseModel):
    """First SSE event — contains conversation and request metadata."""

    type: str = "meta"
    conversation_id: UUID
    request_id: UUID


class ChatTokenEvent(BaseModel):
    """SSE event for each streamed token."""

    type: str = "token"
    text: str


class ChatDoneEvent(BaseModel):
    """Final SSE event — marks stream completion with usage stats."""

    type: str = "done"
    usage: dict[str, object] = Field(default_factory=dict)
