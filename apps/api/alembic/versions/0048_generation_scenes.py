# apps/api/alembic/versions/0048_generation_scenes.py
"""generation_requests.scenes JSONB column (PLAN-001 — ADR-096).

Adds the nullable ``scenes`` JSONB column that carries the structured
scene snapshot for scene-by-scene writing (spec §8.2): the POST payload
(``GenerateRequest.scenes``) is persisted verbatim at ``start_generation``
so the request row is the single state carrier between POST and stream —
"what you approved is what streams". NULL means a legacy scene-less
request (the old ``parse_scenes(outline)`` path keeps working).

Downgrade = symmetric column drop. Lossy BY DESIGN for the snapshot data
(it lives only in this column, so it cannot be restored): the snapshot is
ephemeral request-scoped stream state, not durable user content — durable
scene plans live in ``scene_plans`` (0047). The row itself and all other
columns survive both directions untouched.

RULE-14: lands in the SAME task as the ``GenerationRequest.scenes`` ORM
column.

See:
    docs/superpowers/specs/2026-10-09-plan001-scene-planning-design.md (§8.2).
    ADR-096 (scene-planning decisions).

Revision ID: 0048_generation_scenes
Revises: 0047_scene_plans
Create Date: 2026-10-10 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0048_generation_scenes"
down_revision: str | None = "0047_scene_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_requests",
        sa.Column("scenes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generation_requests", "scenes")
