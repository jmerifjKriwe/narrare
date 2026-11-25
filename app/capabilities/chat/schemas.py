"""Request and response shapes for the chat capability."""

from datetime import datetime  # noqa: TC003  Pydantic resolves these at runtime
from typing import Literal, Self
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    """One writer turn: what the panel sent, and the choice it named.

    ``text`` may be empty only for ``accept-suggestion``: there the server
    stores the settled suggestion's own text, never the client's words.
    """

    text: str = Field(max_length=4000)
    act: TurnAct | None = None

    @model_validator(mode="after")
    def _text_required_unless_accepting(self) -> Self:
        """Every other act needs the writer's text; accepting may send none."""
        if not self.text and self.act != "accept-suggestion":
            raise ValueError("the turn needs text")
        return self


class SuggestedParts(BaseModel):
    """Which slot values the model proposed rather than the writer.

    A list slot carries its provenance per item: the values that are suggested.
    """

    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
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


class SessionSummary(BaseModel):
    """One row of the novel's session list: identity, type and the draft's name.

    The list renders a header and a state per session, so it carries no
    proposal — opening the session reads the transcript and the draft.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    mode: str
    entity_type: str | None
    target_id: UUID | None
    name: str | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


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
    """The session with its transcript, up to the read limit, oldest first."""

    turns: list[TurnRead]


class SessionList(BaseModel):
    """The novel's interviews: open first, then closed, newest first in each state."""

    items: list[SessionSummary]


class TurnReadback(BaseModel):
    """What one turn answered: the reply, the merged proposal, the suggestion."""

    reply: str | None
    proposal: Proposal | None
    suggestion: str | None
    seq: int
