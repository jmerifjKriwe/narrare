"""Planning domain — SQLAlchemy model for chapter outlines."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class ChapterOutline(Base):
    """Per-chapter outline data for the storyboard feature.

    Stores the stage assignment within the novel's chosen story structure,
    planned beats (JSONB), and free-form outline notes.

    One outline per chapter (UNIQUE constraint on chapter_id).
    """

    __tablename__ = "chapter_outlines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapter_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    stage_assignment: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    planned_beats: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    outline_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"ChapterOutline(id={self.id}, chapter_id={self.chapter_id}, "
            f"stage={self.stage_assignment!r})"
        )
