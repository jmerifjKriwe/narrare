"""Request and response shapes for the chat capability."""

from typing import Literal
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class SourceRead(BaseModel):
    chunk_id: UUID
    document_title: str
    text: str


class EmbeddingMismatchDetail(BaseModel):
    """Identify incompatible stored and current embedding widths."""

    code: Literal["embedding-mismatch"]
    stored: int
    found: int


class EmbeddingMismatchRead(BaseModel):
    """The HTTP 409 body returned when source embeddings are incompatible."""

    detail: EmbeddingMismatchDetail
