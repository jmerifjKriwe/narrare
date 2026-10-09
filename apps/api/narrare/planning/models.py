"""Planning domain — SQLAlchemy models for chapter outlines and timeline events."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
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


class TimelineEvent(Base):
    """Persistent timeline event for narrative temporal tracking.

    Stores individual events in a novel's timeline, supporting both
    manually created events and AI-generated ones. References KB entities
    (characters, locations) via UUID for cross-feature integration (AD-1).
    """

    __tablename__ = "timeline_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, default="plot_point")

    # Temporal data
    timestamp_raw: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    timestamp_normalized: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    temporal_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Chapter reference (optional — event may not map to a specific chapter)
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # KB entity references (hybrid model — AD-1)
    # Each ref has both ID (for KB linkage) and name (for display)
    # [{"id": "uuid-string", "name": "John Smith"}, ...]
    character_refs: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    # {"id": "uuid-string", "name": "The Castle"} or null
    location_ref: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    # Causal links (free text or UUID references to other events)
    causes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    consequences: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Provenance
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    # NULL for manual, 0.0-1.0 for AI
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # FALSE for extracted events pending user review
    is_confirmed: Mapped[bool] = mapped_column(nullable=False, default=True)

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
            f"TimelineEvent(id={self.id}, novel_id={self.novel_id}, "
            f"name={self.event_name!r}, order={self.temporal_order})"
        )


class ScenePlan(Base):
    """One planned scene in a chapter's scene plan (PLAN-001 — ADR-096).

    First-class replacement for ``chapter_outlines.planned_beats``: ordered
    scenes with a consecutive ``position`` (1..N). Consecutiveness is an
    application invariant enforced by the aggregate diff-sync, not a DB
    constraint — a UNIQUE (chapter_id, position) would fight reordering.

    References KB entities via hybrid refs (TimelineEvent / AD-1 pattern):
    ``{"id": "<uuid>", "name": "..."}`` — the id links to the KB entry, the
    name keeps display alive when the entry is deleted. Refs are user
    content and never rewritten (RULE-22 §7).
    """

    __tablename__ = "scene_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    # Hybrid KB refs (TimelineEvent / AD-1 pattern) — ref dict or null
    # {"id": "uuid-string", "name": "John Smith"} or null
    pov_character_ref: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    location_ref: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    # [{"id": "uuid-string", "name": "John Smith", "goal": "warn the guard"}, ...]
    present_characters: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list
    )

    purpose: Mapped[str] = mapped_column(Text, nullable=False, default="")
    conflict: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resolution: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Ordered key events — plain strings
    beats: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    # planned | in_progress | complete
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")

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
            f"ScenePlan(id={self.id}, chapter_id={self.chapter_id}, "
            f"position={self.position}, title={self.title!r})"
        )
