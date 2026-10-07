# apps/api/alembic/versions/0044_budget_settings.py
"""user_ai_settings budget columns (STATS-002 budgets, ADR-094).

Two typed columns on ``user_ai_settings`` (binding spec A-5):

- ``monthly_budget_usd NUMERIC(10,2) NULL`` — NULL = no budget (the
  default state: the pre-call gate is a no-op without a budget).
  Deliberately NO server_default so existing rows stay budget-less.
- ``budget_mode TEXT NOT NULL DEFAULT 'warn'`` — 'warn' (badge only,
  safe default) or 'block' (hard 429 at/over budget). The server
  default backfills existing rows during ADD COLUMN; a named CHECK
  keeps the value in {'warn', 'block'} — house precedent
  ``ck_notes_note_type`` (0041), mirrored by the model's
  ``__table_args__`` (RULE-14: model + migration land together).

RULE-14: lands in the SAME task batch as the ``UserAiSettings`` model
columns. upgrade()/downgrade() are symmetric: add 2 columns + 1 CHECK
vs drop CHECK + 2 columns.

See:
    docs/superpowers/specs/2026-10-07-stats002-budgets-design.md (A-5).
    ADR-094 (storage decision: typed columns, not a JSONB blob).
    0041_notes / 0043_usage_records — layout mirrored here.

Revision ID: 0044_budget_settings
Revises: 0043_usage_records
Create Date: 2026-10-07 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0044_budget_settings"
down_revision: str | None = "0043_usage_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── budget columns (A-5): NULL budget = gate no-op; warn = default ────
    op.add_column(
        "user_ai_settings",
        sa.Column("monthly_budget_usd", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "user_ai_settings",
        sa.Column(
            "budget_mode",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'warn'"),
        ),
    )
    op.create_check_constraint(
        "ck_user_ai_settings_budget_mode",
        "user_ai_settings",
        "budget_mode IN ('warn', 'block')",
    )


def downgrade() -> None:
    # Reverse of upgrade(): drop the CHECK, then both columns. A downgrade
    # is an explicit user action that removes the feature — budget values
    # are re-enterable user settings, not irreplaceable telemetry.
    op.drop_constraint("ck_user_ai_settings_budget_mode", "user_ai_settings", type_="check")
    op.drop_column("user_ai_settings", "budget_mode")
    op.drop_column("user_ai_settings", "monthly_budget_usd")
