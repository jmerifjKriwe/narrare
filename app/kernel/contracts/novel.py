"""Shared domain vocabulary: novels and chapters."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.kernel.db.base import UserOwned


class Novel(UserOwned):
    __tablename__ = "novels"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200))
    genre: Mapped[str | None] = mapped_column(String(80))
    blurb: Mapped[str | None] = mapped_column(Text)
    # The export's front matter. The language is a BCP-47-ish code (`de`,
    # `en`); both are nullable — a novel without an answer does not lie.
    author: Mapped[str | None] = mapped_column(String(200))
    language: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    # The export's trace: set by every successful export (WP6 D1) and by
    # nothing else — no ``onupdate`` — so an edit makes it honestly stale.
    last_exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Chapter(UserOwned):
    __tablename__ = "chapters"
    # One number per chapter in a book: positions are allocated under the
    # parent's lock, and this is what makes the invariant the table's rather
    # than the caller's (#521). Deferrable, because a renumber (WP6: a
    # reorder, a delete's close-up) passes through states the plain form
    # refuses — the check belongs at commit, where the set is consistent.
    __table_args__ = (
        UniqueConstraint("novel_id", "position", deferrable=True, initially="DEFERRED"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    position: Mapped[int]
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
