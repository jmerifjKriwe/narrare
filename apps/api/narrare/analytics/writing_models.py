# apps/api/narrare/analytics/writing_models.py
"""WritingActivityEventRow SQLAlchemy model — STATS-001 writing stats.

Mirrors migration 0045_writing_activity_events (RULE-14: model + migration
land together). One append-only signed delta event per content-write
surface (ADR-095: NO snapshots, NO session tracking, NO aggregates stored).

``delta_words`` is deliberately signed without a CHECK — chapter deletes
produce honest negative deltas and both signs are valid data.
``created_at`` carries the recorder's write-time timestamp (ADR-095 D1) —
deliberately NO server/default so late sink writes cannot drift, mirroring
``UsageRecordRow``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class WritingActivityEventRow(Base):
    """One signed word-count delta captured from a content-write surface."""

    __tablename__ = "writing_activity_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Deleting a user must not silently erase writing history — RESTRICT
    # forces an explicit decision (ADR-095 D1, usage_records precedent).
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Writing history outlives the novel (ON DELETE SET NULL, ADR-095 D1).
    novel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Chapter deletion is a NORMAL flow: the delta event survives with a
    # nulled reference (ON DELETE SET NULL, ADR-095 D1).
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Signed: deletes emit negative deltas — deliberately NO CHECK (both
    # signs valid, ADR-095 D1).
    delta_words: Mapped[int] = mapped_column(Integer, nullable=False)
    # Set from the recorder at write time (ADR-095 D1) — no default, so late
    # sink writes cannot drift.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # Day bucketing / streak windows per user (read side, Task E4).
        Index("ix_writing_activity_events_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"WritingActivityEventRow(id={self.id}, delta_words={self.delta_words}, "
            f"created_at={self.created_at!r})"
        )
