# apps/api/alembic/versions/0041_notes.py
"""notes table (NOTES-001 Scratchpad).

Creates the novel-independent scratchpad: markdown content, language-neutral
type key, free-form TEXT[] tags (GIN-indexed for autocomplete/containment),
and OPTIONAL single links to a novel OR a series — never both
(``ck_notes_scope_invariant``, the ADR-075-style scope pattern with
deliberately different NULL semantics: both NULL = global note, the normal
case). Links are ``ON DELETE SET NULL`` — the note outlives the entity.

RULE-14: lands in the SAME task batch as the ``Note`` model. The
upgrade/downgrade pair is atomic: one create_table (+ indexes) vs
drop_index x5 + drop_table — symmetric by construction.

See:
    docs/superpowers/specs/2026-08-21-scratchpad-design.md §4.
    0037_series_foundation — the scope-invariant CHECK pattern mirrored here.
    0040_series_drift_results — the migration file layout mirrored here.

Revision ID: 0041_notes
Revises: 0040_series_drift_results
Create Date: 2026-08-21 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0041_notes"
down_revision: str | None = "0040_series_drift_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── notes table (global scratchpad, optional single scope link) ────────
    op.create_table(
        "notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("note_type", sa.Text(), nullable=False, server_default=sa.text("'idea'")),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "novel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("novels.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "series_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("series.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "NOT (novel_id IS NOT NULL AND series_id IS NOT NULL)",
            name="ck_notes_scope_invariant",
        ),
        sa.CheckConstraint(
            "note_type IN ('idea', 'concept', 'question', 'other')",
            name="ck_notes_note_type",
        ),
    )
    op.create_index("ix_notes_user_id", "notes", ["user_id"])
    op.create_index("ix_notes_novel_id", "notes", ["novel_id"])
    op.create_index("ix_notes_series_id", "notes", ["series_id"])
    op.create_index("ix_notes_tags", "notes", ["tags"], postgresql_using="gin")
    op.create_index("ix_notes_user_updated", "notes", ["user_id", "updated_at"])


def downgrade() -> None:
    # Reverse of upgrade(): drop indexes then the table. A downgrade is an
    # explicit user action that removes the feature (spec §4 note).
    op.drop_index("ix_notes_user_updated", table_name="notes")
    op.drop_index("ix_notes_tags", table_name="notes")
    op.drop_index("ix_notes_series_id", table_name="notes")
    op.drop_index("ix_notes_novel_id", table_name="notes")
    op.drop_index("ix_notes_user_id", table_name="notes")
    op.drop_table("notes")
