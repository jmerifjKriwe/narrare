"""Band summaries table + series_settings.context_window_size (Spec 2, Task 1).

Spec 2 (Series Generation Context) Task 1 — the Alembic migration that
materialises the schema changes for the BandSummary feature in one atomic
file (RULE-14: a migration lands in the SAME task batch as its model
changes; no ``Base.metadata.create_all()`` in integration tests).

What this migration does, in order:

1. Create ``band_summaries`` — the 1:1 companion to ``novels``.
   ``novel_id`` is both the PRIMARY KEY and a UNIQUE FOREIGN KEY
   (``ON DELETE CASCADE``), so there is at most one summary row per novel
   and deleting a novel removes its summary. ``full_summary`` /
   ``short_summary`` are produced by the BandSummaryAgent (Spec 2, Task 2);
   ``override`` is an optional user-supplied text that takes precedence at
   assembly time. ``generated_at`` defaults to ``now()`` for non-ORM inserts.
2. ALTER ``series_settings``: add ``context_window_size INTEGER NOT NULL
   DEFAULT 3`` — the recency-window read by SeriesHistoryTier (Spec 2,
   Task 6) to decide how many preceding bands get a full summary. Existing
   rows backfill to 3 via the server_default.

Design notes
------------
Mirrors the established slice pattern (see 0037): DB-level defaults are
expressed here as ``server_default`` for non-ORM inserts / backfill, while
the ORM model also carries the matching default for ORM-initiated inserts.
``alembic check`` is not run in CI; the migration correctness gate is
``alembic upgrade head`` (CI + ``tests/integration/conftest.py``).

See:
    Spec 2 design doc — Series Generation Context.
    ADR-076 — Band summaries & series history tier.
    0037_series_foundation — the slice/migration pattern mirrored here.

Revision ID: 0038_band_summaries
Revises: 0037_series_foundation
Create Date: 2026-08-02 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0038_band_summaries"
down_revision: str | None = "0037_series_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. band_summaries table (1:1 to novels, novel_id IS the PK) ───────
    op.create_table(
        "band_summaries",
        sa.Column(
            "novel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("novels.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            primary_key=True,
        ),
        sa.Column("full_summary", sa.Text, nullable=True),
        sa.Column("short_summary", sa.Text, nullable=True),
        sa.Column("override", sa.Text, nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── 2. series_settings: recency-window column ─────────────────────────
    # NOT NULL with server_default so existing rows backfill to 3 (the default
    # band count for the SeriesHistoryTier full-summary window).
    op.add_column(
        "series_settings",
        sa.Column(
            "context_window_size",
            sa.Integer,
            nullable=False,
            server_default="3",
        ),
    )


def downgrade() -> None:
    # Reverse order of upgrade(). Each step mirrors its upgrade counterpart.
    # ── 2. Drop series_settings.context_window_size ───────────────────────
    op.drop_column("series_settings", "context_window_size")

    # ── 1. Drop band_summaries table ──────────────────────────────────────
    op.drop_table("band_summaries")
