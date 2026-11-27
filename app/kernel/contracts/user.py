"""Shared domain vocabulary: the user."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.kernel.db.base import Base
from app.kernel.language_tag import LANGUAGE_TAG_MAX_LENGTH


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    # NULL means "follow the browser": a user who never chose has no opinion,
    # and the client decides from navigator.languages. A tag the catalog does
    # not carry is refused at the API, not stored.
    locale: Mapped[str | None] = mapped_column(String(LANGUAGE_TAG_MAX_LENGTH))
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
    # The update check's state (design 2026-11-24): how often the app asks, when
    # it last did, and what it last heard. The interval is the user's answer;
    # seven days is the product default. The last-known fields keep the answer
    # readable when the release source is offline, and the dismissed version is
    # the one banner the reader asked to stop seeing.
    update_check_interval_days: Mapped[int] = mapped_column(default=7, server_default="7")
    last_update_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_update_version: Mapped[str | None] = mapped_column(String(64))
    last_known_latest_version: Mapped[str | None] = mapped_column(String(64))
    last_known_release_notes: Mapped[str | None] = mapped_column(Text)
    last_known_release_url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
