"""SeriesDriftResult SQLAlchemy model (SERIES-004 Slice 6 — C2 drift persistence).

A ``SeriesDriftResult`` is the LATEST persisted drift snapshot for one novel
(band): canon-contradiction result AND series-voice-drift result as ONE
composite JSON document. It is a strict 1:1 companion to ``Novel``
(``novel_id`` is both the primary key and the unique key — the
``band_summaries`` pattern), enforcing the latest-wins history model:
exactly one record per novel, new runs overwrite their section, no history
rows.

``result`` holds the keys ``consistency`` (a serialized
``SeriesConsistencyCheckResponse``) and ``voice_drift`` (a serialized
``AuthorVoiceDriftResponse``); each check run upserts only its own key (the
repository's atomic JSONB-merge upsert — the panel fires both checks in
parallel). ``input_fingerprint`` is the privacy-safe ADR-045-scheme digest
over the band's chapter texts at write time; ``generated_at`` stamps the
last completed write of either check.

This model is intentionally separate from ``series/models.py`` (RULE-06: one
responsibility per file) — that file owns series membership/settings, while
persisted drift snapshots are a Slice-6 persistence concern (the
``band_summary_models.py`` precedent).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class SeriesDriftResult(Base):
    """Latest persisted drift snapshot for one novel (1:1 to Novel).

    ``novel_id`` is the primary key (and unique), enforcing the latest-wins
    model. Deletion cascades from the novel, so a deleted novel takes its
    snapshot with it.
    """

    __tablename__ = "series_drift_results"

    novel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        primary_key=True,
    )
    result: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    input_fingerprint: Mapped[str] = mapped_column(String(length=64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"SeriesDriftResult(novel_id={self.novel_id})"
