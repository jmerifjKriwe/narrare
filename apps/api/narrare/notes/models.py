# apps/api/narrare/notes/models.py
"""Note SQLAlchemy model — NOTES-001 Scratchpad.

Mirrors migration 0041_notes (RULE-14: model + migration land together).
A note is global by default; optionally linked to ONE novel OR ONE series
(never both — ``ck_notes_scope_invariant``). Links are ON DELETE SET NULL:
the note outlives the linked entity (spec §4).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class Note(Base):
    """A scratchpad note (markdown text + type + free tags)."""

    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Ownership follows the Series pattern: plain UUID column + index, no FK.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    note_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="idea", server_default=text("'idea'")
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    novel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("series.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        # Scope invariant — mirrors ck_kb_entries_scope_invariant (0037), but
        # with deliberately different semantics: both NULL = GLOBAL note,
        # the normal case (spec §4).
        CheckConstraint(
            "NOT (novel_id IS NOT NULL AND series_id IS NOT NULL)",
            name="ck_notes_scope_invariant",
        ),
        CheckConstraint(
            "note_type IN ('idea', 'concept', 'question', 'other')",
            name="ck_notes_note_type",
        ),
        # Tag autocomplete prefix filters + containment lookups.
        Index("ix_notes_tags", "tags", postgresql_using="gin"),
        Index("ix_notes_user_updated", "user_id", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"Note(id={self.id}, note_type={self.note_type!r})"
