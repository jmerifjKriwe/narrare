"""SQLAlchemy models for generation module.

Includes GenerationRequest (AI generation jobs) and GraphRun
(WritingGraph checkpoint persistence).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class GenerationRequest(Base):
    """Tracks an AI chapter generation job from start to completion.

    Mirrors the ORM model in narrare.writing.models — this definition
    is kept for Alembic autodetection in the generation module.
    """

    __tablename__ = "generation_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    mode: Mapped[str] = mapped_column(String(30), nullable=False)
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tokens_used: Mapped[int] = mapped_column(nullable=False, default=0)
    word_count: Mapped[int] = mapped_column(nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    novel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class GraphRun(Base):
    """Persisted WritingGraph run with checkpoint data.

    Stores serialized WritingState as JSONB at each checkpoint.
    chapter_id is nullable because graph runs can be started before
    a chapter is assigned (e.g. during outlining).
    """

    __tablename__ = "graph_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    checkpoint_data: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"GraphRun(id={self.id}, run_id={self.run_id!r}, status={self.status!r})"
