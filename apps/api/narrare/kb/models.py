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
    novel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
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
    embeddings_dirty: Mapped[bool] = mapped_column(default=False, nullable=False)
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
        UniqueConstraint("novel_id", "slug", name="uq_kb_entries_novel_slug"),
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
