"""Scene-plan substrate: one planned scene per row.

A scene plan is the writer's per-scene note for a chapter — what the scene
is for, its conflict, how it resolves, and its beats in order. The hybrid
KB references (POV, location, present characters) and the AI draft/refine
assistants are deliberately deferred: this slice ships the row shape the
dock will read and write, nothing more.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
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
