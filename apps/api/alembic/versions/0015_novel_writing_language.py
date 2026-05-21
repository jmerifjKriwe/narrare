"""Rename novels.language to novels.writing_language and widen to String(100).

The novel language field is renamed from `language` to `writing_language`
to distinguish it from UI language. The column type is widened from
String(10) to String(100) to support freetext descriptions like
"Australisches Englisch".

Revision ID: 0015_novel_writing_language
Revises: 0014_graph_runs
Create Date: 2026-05-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0015_novel_writing_language"
down_revision = "0014_graph_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename language column and widen the string length."""
    op.alter_column(
        "novels",
        "language",
        new_column_name="writing_language",
        type_=sa.String(100),
        existing_type=sa.String(10),
    )


def downgrade() -> None:
    """Revert writing_language back to language with String(10)."""
    op.alter_column(
        "novels",
        "writing_language",
        new_column_name="language",
        type_=sa.String(10),
        existing_type=sa.String(100),
    )
