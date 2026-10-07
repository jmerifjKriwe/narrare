# apps/api/alembic/versions/0045_writing_activity_events.py
"""writing_activity_events table (STATS-001 writing stats, ADR-095).

One append-only signed delta event per content-write surface (editor PATCH
incl. version-restore, chapter delete, co-author apply, import commit —
ADR-095 D3). NO snapshots, NO session tracking, NO aggregates stored; the
read side derives dailies/streaks at query time (spec E-3).

``user_id`` is ON DELETE RESTRICT: writing history must not vanish with a
user without an explicit decision (usage_records precedent). ``novel_id``
and ``chapter_id`` are ON DELETE SET NULL: history outlives the novel, and
chapter deletion is a normal flow whose delete event survives with a nulled
reference (ADR-095 D1). ``delta_words`` is signed WITHOUT a CHECK — deletes
are honest negative deltas. ``created_at`` carries the recorder's write-time
timestamp — deliberately NO server_default so late sink writes cannot drift
(ADR-095 D1, mirroring 0043).

RULE-14: lands in the SAME task batch as the ``WritingActivityEventRow``
model. The upgrade/downgrade pair is atomic: one create_table (+ 2 indexes)
vs drop_index x2 + drop_table — symmetric by construction.

See:
    docs/superpowers/specs/2026-10-07-stats001-writing-stats-design.md (E-1).
    ADR-095 (delta-event capture decision).
    0043_usage_records — the migration file layout mirrored here.

Revision ID: 0045_writing_activity_events
Revises: 0044_budget_settings
Create Date: 2026-10-07 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0045_writing_activity_events"
down_revision: str | None = "0044_budget_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── writing_activity_events (append-only signed word deltas) ──────────
    op.create_table(
        "writing_activity_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "novel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("novels.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("delta_words", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_writing_activity_events_user_created",
        "writing_activity_events",
        ["user_id", "created_at"],
    )
    op.create_index("ix_writing_activity_events_novel_id", "writing_activity_events", ["novel_id"])


def downgrade() -> None:
    # Reverse of upgrade(): drop indexes then the table. A downgrade is an
    # explicit user action that removes the feature (writing telemetry is
    # non-critical, derived data — the recorder can only regenerate it from
    # now on, never retroactively).
    op.drop_index("ix_writing_activity_events_novel_id", table_name="writing_activity_events")
    op.drop_index("ix_writing_activity_events_user_created", table_name="writing_activity_events")
    op.drop_table("writing_activity_events")
