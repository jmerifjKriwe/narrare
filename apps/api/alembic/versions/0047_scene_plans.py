# apps/api/alembic/versions/0047_scene_plans.py
"""scene_plans table + planned_beats backfill (PLAN-001 — ADR-096).

Creates the first-class ``scene_plans`` substrate that replaces
``chapter_outlines.planned_beats``: one row per planned scene, ordered by a
consecutive ``position`` (application invariant — deliberately no UNIQUE
(chapter_id, position), so reordering stays a plain per-row UPDATE).

Backfill semantics (spec §3.3): for every ``chapter_outlines`` row, each old
beat at list index i becomes ONE scene — ``position=i+1``,
``title=beat.title``, ``purpose=beat.description``,
``status="complete" if beat.completed else "planned"``, every other column
left empty/default. The historical ``planned_beats`` shape "is not locked
down across all creators", so the backfill is tolerant: non-dict beats are
skipped and missing keys fall back to defaults.

``gen_random_uuid()`` supplies new PKs — a PostgreSQL 13+ builtin (verified
on the project's PostgreSQL 17; already relied on by 0013/0014/0022/0028/0031).

Downgrade = drop table + index (lossless: ``planned_beats`` still exists at
this revision's parent — the column itself is dropped only in 0049).

RULE-14: lands in the SAME task as the ``ScenePlan`` ORM model.

See:
    docs/superpowers/specs/2026-10-09-plan001-scene-planning-design.md (§3).
    ADR-096 (scene-planning decisions).

Revision ID: 0047_scene_plans
Revises: 0046_writing_goals
Create Date: 2026-10-09 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0047_scene_plans"
down_revision: str | None = "0046_writing_goals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scene_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("pov_character_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("location_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "present_characters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("purpose", sa.Text(), nullable=False, server_default=""),
        sa.Column("conflict", sa.Text(), nullable=False, server_default=""),
        sa.Column("resolution", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "beats",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="planned"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_scene_plans_chapter_id", "scene_plans", ["chapter_id"])

    # Backfill: one scene per old beat (tolerant of arbitrary JSONB shapes —
    # the planned_beats shape is not locked down across all creators).
    conn = op.get_bind()
    outlines = conn.execute(
        sa.text("SELECT id, chapter_id, planned_beats FROM chapter_outlines")
    ).mappings()
    for row in outlines:
        for i, beat in enumerate(row["planned_beats"] or [], start=1):
            if not isinstance(beat, dict):
                continue
            conn.execute(
                sa.text(
                    "INSERT INTO scene_plans (id, chapter_id, position, title, purpose, status)"
                    " VALUES (gen_random_uuid(), :chapter_id, :position, :title, :purpose, :status)"
                ),
                {
                    "chapter_id": row["chapter_id"],
                    "position": i,
                    "title": str(beat.get("title", "") or "")[:500],
                    "purpose": str(beat.get("description", "") or ""),
                    "status": "complete" if beat.get("completed") else "planned",
                },
            )


def downgrade() -> None:
    op.drop_index("ix_scene_plans_chapter_id", table_name="scene_plans")
    op.drop_table("scene_plans")
