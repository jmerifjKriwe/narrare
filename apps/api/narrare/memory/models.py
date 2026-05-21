"""SQLAlchemy model for feedback_events table."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
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


class FeedbackEventModel(Base):
    """Persisted feedback event on an AI suggestion."""

    __tablename__ = "feedback_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    suggestion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    intent: Mapped[str] = mapped_column(String(50), nullable=False)
    suggestion_text: Mapped[str] = mapped_column(Text, nullable=False)
    modification: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now
    )

    __table_args__ = (Index("ix_feedback_events_user_project", "user_id", "project_id"),)

    def __repr__(self) -> str:
        return f"FeedbackEventModel(id={self.id}, user_id={self.user_id}, action={self.action!r})"


class PreferenceProfileModel(Base):
    """Learned preference profile derived from feedback events."""

    __tablename__ = "preference_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    style_patterns: Mapped[list[object]] = mapped_column(JSONB, default=list, server_default="[]")
    content_patterns: Mapped[list[object]] = mapped_column(JSONB, default=list, server_default="[]")
    avoidance_patterns: Mapped[list[object]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    event_count_at_analysis: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_preference_profiles_user_project"),
    )

    def __repr__(self) -> str:
        return (
            f"PreferenceProfileModel(id={self.id}, "
            f"user_id={self.user_id}, project_id={self.project_id})"
        )
