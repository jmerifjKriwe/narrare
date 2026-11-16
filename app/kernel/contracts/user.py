"""Shared domain vocabulary: the user."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.kernel.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    # NULL means "follow the browser": a user who never chose has no opinion,
    # and the client decides from navigator.languages. A tag the catalog does
    # not carry is refused at the API, not stored.
    locale: Mapped[str | None] = mapped_column(String(8))
    # NULL means "follow the system": the browser's `prefers-color-scheme`
    # decides. A stored value is the reader's own answer and wins over it.
    theme: Mapped[str | None] = mapped_column(String(8))
    # The profile's author name (W4 D9/D22) — the user block's label, distinct
    # from the per-book ``Novel.author`` running head. Nullable: a user who
    # never answered falls back to the email label, not to a lie.
    author_name: Mapped[str | None] = mapped_column(String(200))
    # The atelier-level daily word goal (W4 D8) — user scope, not per book;
    # the shelf banner reads it. Nullable: no goal set is an honest neutral.
    daily_goal_words: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
