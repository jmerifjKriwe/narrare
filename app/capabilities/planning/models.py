"""Scene-plan substrate: one planned scene per row.

A scene plan is the writer's per-scene note for a chapter — what the scene
is for, its conflict, how it resolves, and its beats in order. The hybrid
KB references (POV, location, present characters) and the AI draft/refine
assistants are deliberately deferred: this slice ships the row shape the
dock will read and write, nothing more.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.kernel.db.base import UserOwned

SCENE_STATUSES = ("planned", "in_progress", "complete")
"""The scene lifecycle's three states. A short tuple in code, not a PG enum
and not a table: the set is fixed by the planning contract, not by data.
A scene is born ``planned`` and the writer moves it by hand.
"""


class ScenePlan(UserOwned):
    """One planned scene of a chapter, in manual lifecycle order.

    ``position`` is the scene's order within the chapter; the aggregate
    write path renumbers it, so the column carries no uniqueness of its
    own. ``beats`` is the ordered beat list, as a JSON column — no child
    table. The chapter foreign key cascades, so deleting a chapter takes
    its plans along.
    """

    __tablename__ = "scene_plans"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chapter_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    title: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str] = mapped_column(Text, default="")
    conflict: Mapped[str] = mapped_column(Text, default="")
    resolution: Mapped[str] = mapped_column(Text, default="")
    beats: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # One of SCENE_STATUSES.
    status: Mapped[str] = mapped_column(String(16), default="planned")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class TimelineEvent(UserOwned):
    """One hand-placed event on a novel's timeline, in the writer's own order.

    ``position`` is the event's manual order on the canvas; null means
    unordered — the list answers those rows last. ``date_label`` is the
    optional free-text date ("im dritten Jahr"), never parsed. ``chapter_id``
    is the optional chapter link: deleting the chapter unlinks the event
    (SET NULL), deleting the novel takes its events along. Character refs
    are free-text names for now — KB linkage, AI extraction, consistency
    and ages are deliberate follow-ups, not this slice.
    """

    __tablename__ = "timeline_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int | None] = mapped_column(Integer)
    date_label: Mapped[str] = mapped_column(String(200), default="")
    character_names: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class PlanningNovelSettings(UserOwned):
    """The storyboard's per-novel choice: which structure lays the chapters out.

    One row per novel — ``novel_id`` is the primary key, so the setting is
    replaced, never doubled. Deleting the novel takes its setting along;
    the structure id names a key of the structures registry, defaulting to
    three-act until the writer picks another through the remap confirm.
    """

    __tablename__ = "planning_novel_settings"

    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), primary_key=True
    )
    story_structure: Mapped[str] = mapped_column(String(32), default="three-act")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ChapterStage(UserOwned):
    """One writer-set stage assignment: the chapter's manual storyboard column.

    One row per chapter — ``chapter_id`` is the primary key, so moving a
    chapter rewrites its row. A chapter without a row shows its suggested
    stage instead; the suggestion is computed, never persisted. Deleting
    the chapter takes its assignment along. ``stage_key`` names a stage of
    the novel's current structure; the timestamps stay the server's own.
    """

    __tablename__ = "chapter_stages"

    chapter_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), primary_key=True
    )
    stage_key: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
