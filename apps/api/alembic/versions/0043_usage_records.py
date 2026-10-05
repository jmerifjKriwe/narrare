# apps/api/alembic/versions/0043_usage_records.py
"""usage_records table (STATS-002 AI cost tracking).

One append-only row per observed LLM call: token counts (incl. cache
read/creation), latency and an OPTIONAL estimated cost. ``cost_usd`` NULL
means unpriced (unknown model pricing — strict pricing, spec §3.2).

``user_id`` is ON DELETE RESTRICT: cost history must not vanish with a user
without an explicit decision. ``novel_id`` is ON DELETE SET NULL: cost
history outlives novel deletion (spec §3.4). ``created_at`` carries the
usage event's own timestamp — deliberately NO server_default so late sink
writes cannot drift months (spec §3.4).

RULE-14: lands in the SAME task batch as the ``UsageRecordRow`` model. The
upgrade/downgrade pair is atomic: one create_table (+ 2 indexes) vs
drop_index x2 + drop_table — symmetric by construction.

See:
    docs/superpowers/specs/2026-10-05-stats002-cost-tracking-design.md §3.4.
    0041_notes — the migration file layout mirrored here.

Revision ID: 0043_usage_records
Revises: 0042_chat_project_optional
Create Date: 2026-10-05 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0043_usage_records"
down_revision: str | None = "0042_chat_project_optional"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── usage_records table (append-only LLM cost telemetry) ──────────────
    op.create_table(
        "usage_records",
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
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "cache_creation_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_usage_records_user_created", "usage_records", ["user_id", "created_at"])
    op.create_index("ix_usage_records_novel_id", "usage_records", ["novel_id"])


def downgrade() -> None:
    # Reverse of upgrade(): drop indexes then the table. A downgrade is an
    # explicit user action that removes the feature (cost telemetry is
    # non-critical data — spec §6).
    op.drop_index("ix_usage_records_novel_id", table_name="usage_records")
    op.drop_index("ix_usage_records_user_created", table_name="usage_records")
    op.drop_table("usage_records")
