"""Request and response shapes for the chat capability."""

from datetime import datetime  # noqa: TC003  Pydantic resolves these at runtime
from typing import Literal
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field

from app.capabilities.chat.prompts import RETRIEVAL_LIMIT

TurnAct = Literal[
    "accept-suggestion",
    "no-idea",
    "fill-all",
    "reject-suggestion",
    "drop-suggestions",
]
"""The writer's five choices on a turn, exactly as the wire names them."""


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=RETRIEVAL_LIMIT, ge=1, le=20)


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


class SessionCreate(BaseModel):
    """The door's request: one novel, one mode, and the type the panel fixed."""

    mode: str
    novel_id: UUID
    entity_type: str | None = None
    target_id: UUID | None = None


class TurnCreate(BaseModel):
    """One writer turn: what the panel sent, and the choice it named."""

    text: str = Field(min_length=1, max_length=4000)
    act: TurnAct | None = None


class SuggestedParts(BaseModel):
    """Which slot values the model proposed rather than the writer."""

    aliases: bool = False
    tags: bool = False
    content: bool = False


class ProposedRelation(BaseModel):
    """One proposed relation, with the provenance the server decided."""

    target: str
    type: str
    note: str = ""
    suggested: bool = False


class Proposal(BaseModel):
    """The dialog's draft: the slot set, its marks and the proposed relations."""

    name: str | None = None
    name_suggested: bool = False
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    content: str = ""
    suggested: SuggestedParts = Field(default_factory=SuggestedParts)
    relations: list[ProposedRelation] = Field(default_factory=list[ProposedRelation])


class SessionRead(BaseModel):
    """One interview as every read shows it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    mode: str
    entity_type: str | None
    target_id: UUID | None
    proposal: Proposal | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TurnRead(BaseModel):
    """One transcript line and its suggestion state."""

    model_config = ConfigDict(from_attributes=True)

    seq: int
    role: str
    text: str
    act: str | None
    suggestion: str | None
    suggestion_state: str | None
    created_at: datetime


class SessionDetail(SessionRead):
    """The session with its whole transcript, oldest first."""

    turns: list[TurnRead]


class SessionList(BaseModel):
    """The novel's interviews, newest first."""

    items: list[SessionRead]


class TurnReadback(BaseModel):
    """What one turn answered: the reply, the merged proposal, the suggestion."""

    reply: str | None
    proposal: Proposal | None
    suggestion: str | None
    seq: int
