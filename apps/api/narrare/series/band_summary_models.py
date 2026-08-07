"""BandSummary SQLAlchemy model (Spec 2 — Series Generation Context).

A ``BandSummary`` is the auto-generated + override summary for one novel's
place in a series. It is a strict 1:1 companion to ``Novel``: ``novel_id`` is
both the primary key and the unique key, so there is at most one summary row
per novel. The generation pipeline (Spec 2, Task 3) upserts
``full_summary`` / ``short_summary`` from the BandSummaryAgent; a user may
supply an ``override`` that takes precedence over the generated text at
assembly time (Spec 2, Task 6 SeriesHistoryTier).

This model is intentionally separate from ``series/models.py`` (RULE-06:
one responsibility per file) — that file owns series membership/settings,
while band summaries are a generation-context concern.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class BandSummary(Base):
    """Auto-generated + override band summary for a novel (1:1 to Novel).

    ``novel_id`` is the primary key (and unique), enforcing the 1:1
    relationship: exactly one summary row per novel. Deletion cascades from
    the novel, so a deleted novel takes its summary with it.
    """

    __tablename__ = "band_summaries"

    novel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        primary_key=True,
    )
    full_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    override: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"BandSummary(novel_id={self.novel_id})"
