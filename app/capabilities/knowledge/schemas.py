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


class ReembedResult(BaseModel):
    """What a re-embed rebuilt: every document, every chunk of it."""

    documents: int
    chunks: int


class ExtractionRequest(BaseModel):
    """Which chapter of the novel the worker should read."""

    chapter_id: UUID


class ExtractionAccepted(BaseModel):
    """The enqueue's whole answer: what to poll."""

    job_id: UUID


class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    name: str
    kind: str
    description: str | None
    created_at: datetime


class EntityUpdate(BaseModel):
    """The PATCH body: only the fields present are the change.

    ``None`` is ambiguous by shape alone — an absent field and a cleared
    description both look like None — so the service reads
    ``model_fields_set`` to tell a carried change from a missing one. The
    values are checked there, against the parse contract's vocabulary:
    this schema carries the fields, the contract decides what a value may
    be.
    """

    name: str | None = None
    kind: str | None = None
    description: str | None = None


class EntityMerge(BaseModel):
    """The merge's whole ask: which row survives."""

    target_id: UUID


class SuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    chapter_id: UUID
    name: str
    kind: str
    description: str | None
    status: str
    created_at: datetime
