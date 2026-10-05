# apps/api/narrare/analytics/models.py
"""UsageRecordRow SQLAlchemy model — STATS-002 AI cost tracking.

Mirrors migration 0043_usage_records (RULE-14: model + migration land
together). One append-only row per observed LLM call: token counts (incl.
cache read/creation), latency and an OPTIONAL estimated cost attributed to
a user and, when known, a novel.

``cost_usd`` NULL means "unpriced" (unknown model pricing — strict pricing,
spec §3.2); money is NUMERIC, never float. ``created_at`` carries the usage
event's own timestamp (spec §3.4) — deliberately NO server/default so late
sink writes cannot drift.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class UsageRecordRow(Base):
    """One captured LLM usage event (cost-tracking telemetry)."""

    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Deleting a user must not silently erase cost history — RESTRICT forces
    # an explicit decision (spec §3.4).
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Cost history outlives the novel (ON DELETE SET NULL, spec §3.4).
    novel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    cache_read_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    cache_creation_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    # NULL = unpriced (unknown model pricing); NUMERIC(12,6) — no float money.
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    # Set from the usage event's own timestamp (spec §3.4) — no default.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # Month/period listings and trend buckets per user (repository, Task 8).
        Index("ix_usage_records_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"UsageRecordRow(id={self.id}, intent={self.intent!r}, model_id={self.model_id!r})"
