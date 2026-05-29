"""Wiki tables for precomputed summaries.

Defines ``WikiSummary`` (entity-level wiki) and
``WikiChapterSummary`` (chapter-level wiki).
"""

from __future__ import annotations

import enum
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


class WikiSummaryStatus(enum.StrEnum):
    """Tracks freshness of a wiki summary."""

    PENDING = "pending"
    FRESH = "fresh"
    STALE = "stale"


class WikiSummary(Base):
    """Precomputed LLM-generated wiki summary for a single KB entity.

    One row per entity per novel.  Refreshed when the entity body or
    its dependency graph changes.
    """

    __tablename__ = "wiki_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kb_entries.id", ondelete="CASCADE"), nullable=False
    )
    narrative_summary: Mapped[str] = mapped_column(Text, nullable=False)
    role_in_story: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_attributes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    relationships: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, nullable=True)
    chapter_references: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, nullable=True)
    character_arc: Mapped[str | None] = mapped_column(Text, nullable=True)
    depends_on: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    version: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", server_default=""
    )
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'fresh', 'stale')", name="ck_wiki_summaries_status"),
        UniqueConstraint("novel_id", "entity_id", name="uq_wiki_summary_entity"),
        Index("ix_wiki_summaries_status", "status"),
        Index("ix_wiki_summaries_novel_id", "novel_id"),
    )

    def __repr__(self) -> str:
        return (
            f"WikiSummary(id={self.id}, novel_id={self.novel_id}, "
            f"entity_id={self.entity_id}, status={self.status!r})"
        )


class WikiChapterSummary(Base):
    """Precomputed LLM-generated wiki summary for a single chapter.

    One row per chapter.  Refreshed when the chapter content changes.
    """

    __tablename__ = "wiki_chapter_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    narrative_summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_events: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    entities_involved: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, nullable=True)
    themes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    emotional_arc: Mapped[str | None] = mapped_column(Text, nullable=True)
    chapter_content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", server_default=""
    )
    wiki_prompt_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="1.0.0", server_default="1.0.0"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    version: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'fresh', 'stale')", name="ck_wiki_chapter_status"),
        Index("ix_wiki_chapter_status", "status"),
        Index("ix_wiki_chapter_chapter_id", "chapter_id"),
    )

    def __repr__(self) -> str:
        return (
            f"WikiChapterSummary(id={self.id}, chapter_id={self.chapter_id}, "
            f"status={self.status!r})"
        )
