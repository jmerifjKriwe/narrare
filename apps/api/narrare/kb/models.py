"""Knowledge Base SQLAlchemy models.

Defines ``KBEntry`` for entity instances and ``KBRelationship`` for
the directed/mutual edges between them.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class KBEntry(Base):
    """A single Knowledge Base entity (character, location, etc.)."""

    __tablename__ = "kb_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=True,  # CHANGED: was nullable=False. NULL = Series-Canon entry.
        index=True,
    )
    # Series-Canon scope: when novel_id is NULL, this entry is canon for the series.
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("series.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # For Novel-Overlay entries: optional link to the Series-Canon entry this overlays.
    base_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kb_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(JSONB, default=list, nullable=True)
    # ``metadata`` clashes with SQLAlchemy's MetaData — use Python attr
    # ``metadata_`` mapped to DB column ``metadata``.
    metadata_: Mapped[dict[str, object] | None] = mapped_column(
        "metadata", JSONB, default=dict, nullable=True
    )
    body: Mapped[str | None] = mapped_column(Text, default="", nullable=True)
    template_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        server_default="manual",
        nullable=False,
    )
    review_status: Mapped[str] = mapped_column(
        String(20),
        default="approved",
        server_default="approved",
        nullable=False,
    )
    embeddings_dirty: Mapped[bool] = mapped_column(default=False, nullable=False)
    # Usage tracking for hybrid search scoring (migration 0022_embeddings)
    last_referenced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    usage_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('character', 'concept', 'faction', 'location', "
            "'object', 'setting', 'system', 'timeline')",
            name="ck_kb_entries_entity_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'reviewed', 'canon', 'deprecated')",
            name="ck_kb_entries_status",
        ),
        CheckConstraint(
            "review_status IN ('approved', 'pending', 'rejected')",
            name="ck_kb_entries_review_status",
        ),
        # REMOVED: UniqueConstraint("novel_id", "slug", name="uq_kb_entries_novel_slug")
        # REPLACED BY (in Alembic migration 0036):
        #   - uq_kb_canon_per_series ON (series_id, slug) WHERE novel_id IS NULL
        #   - uq_kb_overlay_per_novel ON (novel_id, slug) WHERE novel_id IS NOT NULL
        #   - ck_kb_entries_scope_invariant CHECK
        Index("ix_kb_entries_entity_type", "entity_type"),
        Index("ix_kb_entries_novel_id", "novel_id"),
        Index("ix_kb_entries_novel_type", "novel_id", "entity_type"),
    )

    def __repr__(self) -> str:
        return f"KBEntry(id={self.id}, name={self.name!r}, type={self.entity_type!r})"


class KBRelationship(Base):
    """A directed or mutual relationship between two KB entries."""

    __tablename__ = "kb_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kb_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kb_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rel_type: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    direction: Mapped[str] = mapped_column(String(10), default="directed", nullable=False)
    metadata_: Mapped[dict[str, object] | None] = mapped_column(
        "metadata", JSONB, default=dict, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "source_id != target_id",
            name="ck_kb_relationships_no_self_ref",
        ),
        CheckConstraint(
            "direction IN ('directed', 'mutual')",
            name="ck_kb_relationships_direction",
        ),
        UniqueConstraint(
            "source_id",
            "target_id",
            "rel_type",
            name="uq_kb_relationships_unique",
        ),
        Index("ix_kb_relationships_source_id", "source_id"),
        Index("ix_kb_relationships_target_id", "target_id"),
    )

    def __repr__(self) -> str:
        return (
            f"KBRelationship(id={self.id}, {self.source_id} -[{self.rel_type}]-> {self.target_id})"
        )
