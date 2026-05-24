"""SQLAlchemy models for embeddings and context usage tracking.

Defines:
- ``Embedding`` — generic vector storage for multiple content types.
- ``ContextUsageEvent`` — tracks user feedback on proactive suggestions.

Uses pgvector's ``Vector`` type for the embedding column.
The ``embeddings`` table supports side-by-side model coexistence via
the ``UNIQUE(source_type, source_id, model)`` constraint.

See: openspec/changes/infra-004-embedding-store/design.md (D1, D7)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class Embedding(Base):
    """A vector embedding for any content source (kb_entry, chapter, etc.).

    The ``UNIQUE(source_type, source_id, model)`` constraint enables
    side-by-side model coexistence during model migration: both old and
    new model embeddings can coexist for the same source entity.
    """

    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)  # type: ignore[assignment]
    model: Mapped[str] = mapped_column(Text, nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_id",
            "model",
            name="uq_embeddings_source_model",
        ),
        Index("idx_embeddings_source", "source_type", "source_id"),
    )

    def __repr__(self) -> str:
        return (
            f"Embedding(id={self.id}, source={self.source_type}:"
            f"{self.source_id}, model={self.model!r})"
        )


class ContextUsageEvent(Base):
    """Tracks user feedback on proactive context suggestions.

    Records accept/dismiss/pin actions so the hybrid search scoring
    can learn from usage patterns over time.

    When a user accepts a suggestion, the caller is responsible for
    incrementing ``kb_entries.usage_count`` and updating
    ``kb_entries.last_referenced_at``.
    """

    __tablename__ = "context_usage_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kb_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('accepted', 'dismissed', 'pinned', 'unpinned')",
            name="ck_context_usage_events_action",
        ),
        CheckConstraint(
            "source IN ('proactive', 'search', 'manual')",
            name="ck_context_usage_events_source",
        ),
        Index("idx_usage_events_entry", "entry_id"),
        Index("idx_usage_events_novel", "novel_id", created_at.desc()),
    )

    def __repr__(self) -> str:
        return (
            f"ContextUsageEvent(id={self.id}, entry={self.entry_id}, "
            f"action={self.action!r}, source={self.source!r})"
        )
