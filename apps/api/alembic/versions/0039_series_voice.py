"""Add use_series_voice boolean column to project_settings (Spec 3 / Task 1).

Adds the per-novel opt-out flag for the Series Voice Hierarchy (Spec 3 —
Delta model: series voice as foundation, novel voice additive). When a novel
belongs to a series, ``use_series_voice`` controls whether the series-level
``author_voice`` is rendered as the base of the ``{{author_voice}}`` slot
(ADR-078). ``TRUE`` by default — series voice is the foundation, so every
novel opts in unless it explicitly opts out.

The column is ``NOT NULL`` with ``server_default`` ``true`` so existing rows
backfill to opt-in during the upgrade (a NOT NULL column added to a populated
table requires a default in PostgreSQL). The ORM model carries the matching
``default=True`` for ORM-initiated inserts — the established dual-default
convention (see ``UserProvider.is_active`` in migration 0001 and the slice
pattern documented in 0037/0038: DB-level defaults as ``server_default`` for
non-ORM inserts / backfill, ORM model carries the matching Python default).

Consumers of this flag land in later tasks (Spec 3 Task 3 extends the novel
settings PATCH; Task 4 extends ``AuthorVoiceConsumer`` with the Delta model).
Until then the column is inert — no runtime behaviour depends on it yet, and
standalone novels are unaffected (no series → flag never read).

RULE-14: this migration lands in the SAME task batch as the
``ProjectSettings`` model change (``use_series_voice`` column). A model
change without a migration is a build failure.

See:
    Spec 3 design doc — Series Voice Hierarchy (Delta model, opt-out).
    ADR-078 — Series Voice Hierarchy.
    migration 0036_author_voice_column — the structural parallel mirrored here
        (per-novel column on ``project_settings``).
    migration 0001_initial — the ``UserProvider.is_active`` boolean+server_default
        pattern mirrored here for backfill.

Revision ID: 0039_series_voice
Revises: 0038_band_summaries
Create Date: 2026-08-05 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0039_series_voice"
down_revision: str | None = "0038_band_summaries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NOT NULL with server_default so existing rows backfill to TRUE (opt-in
    # is the sensible default: series voice is the foundation of the Delta
    # model). Mirrors UserProvider.is_active (migration 0001).
    op.add_column(
        "project_settings",
        sa.Column(
            "use_series_voice",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    # Reverse of upgrade(): drop the opt-out flag added in this migration.
    op.drop_column("project_settings", "use_series_voice")
