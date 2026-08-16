"""series_drift_results table (SERIES-004 Slice 6 — C2 drift persistence).

Creates the latest-wins persistence target for the SERIES-004 cross-novel
drift checks: ONE record per novel (``novel_id`` PK + UNIQUE + FK
``novels.id ON DELETE CASCADE`` — the ``band_summaries`` 1:1 pattern from
0038), holding the composite JSON document (canon conflicts + voice drift as
serialized run-result models) plus the ADR-045-scheme input fingerprint and
the record-level ``generated_at``.

``result`` gets a ``server_default`` of empty jsonb so non-ORM inserts
(backfill tooling) succeed; ORM-initiated inserts carry the matching Python
``default=dict`` (mirroring the 0038/0039 server_default backfill convention).

RULE-14: this migration lands in the SAME task batch as the
``SeriesDriftResult`` model change. A model change without a migration is a
build failure. The upgrade/downgrade pair is atomic: one create_table vs one
drop_table — symmetric by construction.

See:
    docs/superpowers/specs/2026-08-14-post-export-followups-design.md §5 (C2).
    ADR-079 — Series Cross-Novel Drift (Slice 6 amendment).
    0038_band_summaries — the 1:1 novel-companion table pattern mirrored here.

Revision ID: 0040_series_drift_results
Revises: 0039_series_voice
Create Date: 2026-08-16 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0040_series_drift_results"
down_revision: str | None = "0039_series_voice"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── series_drift_results table (1:1 to novels, novel_id IS the PK) ──────
    op.create_table(
        "series_drift_results",
        sa.Column(
            "novel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("novels.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            primary_key=True,
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # Reverse of upgrade(): drop the drift-snapshot table (rows are derived
    # analysis artifacts — safe to lose on downgrade, mirrors 0038).
    op.drop_table("series_drift_results")
