# apps/api/alembic/versions/0049_drop_planned_beats.py
"""Drop ``chapter_outlines.planned_beats`` — PLAN-001 final drop (ADR-096).

``scene_plans`` (0047) is the substrate; after T14-T16 zero readers of the
legacy beats column remain (spec §3.3). Both directions carry the spec's
reverse mapping — one beat per scene, ordered by ``position``:
``title→title``, ``purpose→description``, ``status=="complete"→completed``.

Upgrade:
    1. Reverse-migrate scenes → beats while the column still exists: every
       chapter that has scene rows gets its ``planned_beats`` overwritten
       with the scene-derived projection. Chapters without scenes keep
       their current value (their beats were backfilled into scenes at
       0047; a user's scene deletion is an explicit discard).
    2. ``op.drop_column`` — the legacy column is gone.

Downgrade: recreate the 0013 column shape (JSONB, nullable, server default
``'[]'::jsonb``) and repopulate it with the ONLY restorable projection —
the same scene-derived beats. Documented data loss: the historical
beat-only content is not recoverable, and the projection itself drops the
scene-only fields (conflict/resolution/per-scene beats/hybrid refs — no
beat equivalent). Per ADR-095/0046 a downgrade is an explicit user action.

RULE-14: lands in the SAME task as the ORM column removal.

See:
    docs/superpowers/specs/2026-10-09-plan001-scene-planning-design.md (§3.3).
    ADR-096 (scene-planning decisions).

Revision ID: 0049_drop_planned_beats
Revises: 0048_generation_scenes
Create Date: 2026-10-10 00:00:00.000000
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0049_drop_planned_beats"
down_revision: str | None = "0048_generation_scenes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _write_scene_derived_beats() -> None:
    """Overwrite ``planned_beats`` with beats derived from scene rows.

    Spec §3.3 reverse mapping: for every chapter that has scene plans, the
    outline's beat list becomes one entry per scene (ordered by position).
    The JSON payload is passed as text and CAST to jsonb (plain text bind
    param — no dialect-specific binding needed inside migrations).
    """
    conn = op.get_bind()
    scenes = conn.execute(
        sa.text(
            "SELECT chapter_id, title, purpose, status FROM scene_plans "
            "ORDER BY chapter_id, position"
        )
    ).mappings()
    beats_by_chapter: dict[object, list[dict[str, object]]] = {}
    for row in scenes:
        beats_by_chapter.setdefault(row["chapter_id"], []).append(
            {
                "title": str(row["title"] or ""),
                "description": str(row["purpose"] or ""),
                "completed": str(row["status"] or "") == "complete",
            }
        )
    for chapter_id, beats in beats_by_chapter.items():
        conn.execute(
            sa.text(
                "UPDATE chapter_outlines SET planned_beats = CAST(:beats AS jsonb) "
                "WHERE chapter_id = :chapter_id"
            ),
            {"beats": json.dumps(beats), "chapter_id": chapter_id},
        )


def upgrade() -> None:
    # Spec §3.3: write the last scene-derived beat state while the column
    # still exists, then drop the legacy column.
    _write_scene_derived_beats()
    op.drop_column("chapter_outlines", "planned_beats")


def downgrade() -> None:
    # Recreate the 0013 shape and repopulate with the scene-derived
    # projection (see docstring for the documented data loss).
    op.add_column(
        "chapter_outlines",
        sa.Column(
            "planned_beats",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="[]",
        ),
    )
    _write_scene_derived_beats()
