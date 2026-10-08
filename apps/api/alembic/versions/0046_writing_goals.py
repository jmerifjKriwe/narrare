# apps/api/alembic/versions/0046_writing_goals.py
"""writing_goals JSONB column on project_settings (STATS-001 — ADR-095).

Novel-scoped writing-goal storage, v1 shape ``{"target_words": int | null}``
(exactly one documented key; whole-object replace semantics on PATCH — the
schema boundary rejects unknown keys and non-conforming targets). NULL for
existing rows = "never had a goal"; ``{"target_words": null}`` is the
explicit unset — both read as "no goal" and simply omit the goal block from
``GET /analytics/writing`` (graceful degradation, RULE-11).

Mirrors the ``adaptive_settings`` (0033, ADR-069 D2) and ``author_voice``
(0036, ADR-074) per-novel structured JSONB columns on ``ProjectSettings`` —
the established pattern. A downgrade is an explicit user action that drops
the column WITH its values: goals are re-enterable settings (same argument
as 0044's budget columns), not irreplaceable data.

RULE-14: lands in the SAME task as the ``ProjectSettings.writing_goals``
model column. The upgrade/downgrade pair is atomic: one add_column vs one
drop_column — symmetric by construction.

See:
    docs/superpowers/specs/2026-10-07-stats001-writing-stats-design.md (E-4).
    ADR-095 (writing-stats decisions).
    0036_author_voice_column — the reference implementation mirrored here.

Revision ID: 0046_writing_goals
Revises: 0045_writing_activity_events
Create Date: 2026-10-08 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0046_writing_goals"
down_revision: str | None = "0045_writing_activity_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_settings",
        sa.Column(
            "writing_goals",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("project_settings", "writing_goals")
