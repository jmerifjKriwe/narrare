"""Request and response shapes for the knowledge capability."""

from datetime import datetime  # noqa: TC003  Pydantic resolves these at runtime
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)


class SearchHit(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    text: str
    score: float
