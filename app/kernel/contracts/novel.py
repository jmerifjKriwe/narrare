"""Shared domain vocabulary: novels, chapters and scenes."""

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
    # The setup wizard's per-novel answers. All nullable: a novel without an
    # answer does not lie. The vocabulary the setup schema validates against
    # comes from the Stitch drafts; the template wave pins ``dramatic_form``.
    target_words: Mapped[int | None] = mapped_column()
    author_typology: Mapped[str | None] = mapped_column(String(40))
    dramatic_form: Mapped[str | None] = mapped_column(String(80))
    ai_role: Mapped[str | None] = mapped_column(String(40))
    canon_strictness: Mapped[int | None] = mapped_column()
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
    # The shelf's tracking answers (W3), all nullable — a novel without an
    # answer does not lie. ``status`` is the writing state the shelf's pill
    # names (``draft``, ``revision``, ``final``); the vocabulary is checked
    # at the writing service boundary, not by the column.
    status: Mapped[str | None] = mapped_column(String(20))
    # The series this volume belongs to. SET NULL: a series going away
    # ungroups its books, it does not take them with it.
    series_id: Mapped[UUID | None] = mapped_column(ForeignKey("series.id", ondelete="SET NULL"))
    # The book's number within its series — meaningful only with a series
    # link, which the writing service boundary enforces.
    series_volume: Mapped[int | None] = mapped_column()
    # When the book left the main grid; None is on the shelf. A timestamp,
    # not a flag, so the archive view can say when.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
    # The chapter's own word goal (W4 D8) — distinct from the book's
    # ``Novel.target_words``. Nullable: a chapter without a goal does not lie.
    target_words: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class Scene(UserOwned):
    """The prose unit under a chapter (W4 D1/D2): writing owns the scenes.

    Ownership is the chapters' shape — the row carries ``user_id`` itself and
    the chapter link reaches the novel through it. A chapter going away takes
    its scenes with it (CASCADE); an empty chapter is a real state (D16).
    """

    __tablename__ = "scenes"
    # One number per scene in a chapter: the chapters invariant (#521), the
    # same deferrable form — a reorder passes through states the plain form
    # refuses, so the check belongs at commit, where the set is consistent.
    __table_args__ = (
        UniqueConstraint("chapter_id", "position", deferrable=True, initially="DEFERRED"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    position: Mapped[int]
    # The empty title is the localized placeholder's state (design §5), not a
    # stored label; the prose starts empty the same way.
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    # The drafted overline and in-story datetime: nullable label strings, the
    # ``TimelineEvent.date_label`` pattern — a label, not a timestamp. None is
    # the honest unset, the neutral the UI shows.
    setting: Mapped[str | None] = mapped_column(String(200))
    story_time: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
