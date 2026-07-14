"""Dismissed finding SQLAlchemy model (CR-AUFG-07-26).

Lives in a separate module from ``models.py`` to respect the 200-line
file-size limit (RULE-04 — modularise, don't compress).

See:
    :class:`narrare.kb.consistency_contracts.DismissedFindingProtocol`
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class DismissedFinding(Base):
    """A user-dismissed consistency finding, persisted per novel.

    Identified by a stable ``fingerprint`` (``description::entity_names``)
    rather than ``finding_index`` so that dismissal survives re-runs where
    findings may be added, removed, or reordered.
    """

    __tablename__ = "dismissed_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fingerprint: Mapped[str] = mapped_column(String(512), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    dismissed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "novel_id",
            "fingerprint",
            name="uq_dismissed_novel_fingerprint",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"DismissedFinding(id={self.id}, novel_id={self.novel_id}, "
            f"fingerprint={self.fingerprint!r})"
        )
