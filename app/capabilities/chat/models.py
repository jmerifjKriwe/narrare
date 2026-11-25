"""The interview's two tables: one session per conversation, one turn per line.

Chat owns the conversation's storage, not the canon it proposes — the proposal
is JSON because the dialog's shape is the conversation's own, while an accepted
entity lands through knowledge's endpoint. Every row carries its user (rule 4);
both foreign keys cascade, so a deleted novel takes its interviews and their
turns with it. A turn's ``seq`` is the transcript's monotonic position: allocated
under the session's lock and unique per session by the table, not by a reader.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.kernel.db.base import UserOwned


class AssistantSession(UserOwned):
    """One conversation with the model about one novel.

    ``mode`` names the conversation's contract (``knowledge.entity`` today);
    ``entity_type`` and ``target_id`` carry the interview's subject when the
    writer opened it from the graph, and stay null otherwise. ``proposal`` is
    the dialog's working draft as JSON — written only by the turn's own
    transaction, so an open dialog reads what the last answer left. ``closed_at``
    is the close's timestamp: a closed session keeps its transcript and refuses
    further turns.
    """

    __tablename__ = "assistant_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    # One of the chat modes; the vocabulary is checked at the service boundary.
    mode: Mapped[str] = mapped_column(String(40))
    # One of ENTITY_TYPES when the interview is about an existing subject.
    entity_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[UUID | None] = mapped_column()
    # The dialog's draft: the model's cumulative slots, merged under the lock.
    proposal: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class AssistantTurn(UserOwned):
    """One line of the transcript, in the order the session recorded it.

    ``seq`` is allocated from the session's own counter under its lock, so two
    turns racing on one session land with distinct positions; the unique
    constraint is the table's last word on that. ``act`` names a model act on a
    user turn, ``suggestion`` the pending proposal text on an assistant turn, and
    ``suggestion_state`` its settlement.
    """

    __tablename__ = "assistant_turns"

    __table_args__ = (UniqueConstraint("session_id", "seq", name="uq_assistant_turns_seq"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("assistant_sessions.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column()
    # user | assistant.
    role: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    # One of the plan's acts, on a user turn; null on a plain one.
    act: Mapped[str | None] = mapped_column(String(32))
    suggestion: Mapped[str | None] = mapped_column(Text)
    # pending | accepted | rejected — the suggestion review's states.
    suggestion_state: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
