"""SQLAlchemy models for generation module.

Includes GenerationRequest (AI generation jobs, re-exported from
writing module) and GraphRun (WritingGraph checkpoint persistence).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base
from narrare.writing.models import (
    GenerationRequest,  # noqa: F401  # pyright: ignore[reportUnusedImport]
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
