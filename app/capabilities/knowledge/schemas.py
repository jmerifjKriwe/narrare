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


class ConsistencyAccepted(BaseModel):
    """The check's enqueue answer: what to poll."""

    job_id: UUID


class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    name: str
    type: str
    aliases: list[str]
    tags: list[str]
    content: str
    created_at: datetime
    updated_at: datetime


class EntityUpdate(BaseModel):
    """The PATCH body: only the fields present are the change.

    ``None`` is ambiguous by shape alone — an absent field and a cleared
    content both look like None — so the service reads
    ``model_fields_set`` to tell a carried change from a missing one. The
    values are checked there, against the parse contract's vocabulary and
    the label rules: this schema carries the fields, the contract decides
    what a value may be. A carried ``null`` content clears the body.
    """

    name: str | None = None
    type: str | None = None
    aliases: list[str] | None = None
    tags: list[str] | None = None
    content: str | None = None


class RelationCreate(BaseModel):
    """The POST body of an edge: the other end, a free-text type, a note.

    The type is free text on purpose (D7) — the suggested vocabulary is a
    UI autocomplete, not an API constraint; the service checks blankness
    and length, the ends are taken from the path and this body and are
    immutable afterwards.
    """

    to_entity_id: UUID
    relation_type: str = Field(min_length=1, max_length=80)
    note: str | None = None


class RelationPatch(BaseModel):
    """The PATCH body of an edge: type and note only.

    The ends are immutable — moving an edge is delete plus create — so no
    field here could carry them. ``model_fields_set`` tells a carried
    ``null`` note (cleared) from an absent one (untouched).
    """

    relation_type: str | None = Field(default=None, min_length=1, max_length=80)
    note: str | None = None


class RelationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    from_entity_id: UUID
    to_entity_id: UUID
    relation_type: str
    note: str | None
    created_at: datetime


class EntityMerge(BaseModel):
    """The merge's whole ask: which row survives."""

    target_id: UUID


class SuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    chapter_id: UUID
    name: str
    type: str
    description: str | None
    status: str
    created_at: datetime


class FindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    summary: str
    detail: str | None
    status: str
    created_at: datetime
