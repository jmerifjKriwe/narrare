"""Novel SQLAlchemy model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class Novel(Base):
    __tablename__ = "novels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    genre: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    writing_language: Mapped[str] = mapped_column(String(100), default="en", nullable=False)
    tone: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    story_structure: Mapped[str] = mapped_column(String(100), default="three_act", nullable=False)
    logline: Mapped[str] = mapped_column(Text, default="", nullable=False)
    synopsis: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # Whether this novel was created from demo content
    is_demo: Mapped[bool] = mapped_column(default=False, nullable=False)
    # Series membership (Spec 1, ADR-075). NULL = standalone novel.
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("series.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Position within series (1-based). NULL if not in series.
    series_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Per-novel subtitle (each band has its own identity within a series)
    subtitle: Mapped[str | None] = mapped_column(String(500), nullable=True)
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
        return f"Novel(id={self.id}, title={self.title!r})"
