"""Add chapter_versions table for content versioning.

Revision ID: 0002_chapter_versions
Revises: 0001_initial
Create Date: 2026-05-12 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0002_chapter_versions"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chapter_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="autosave"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_chapter_versions_chapter_id", "chapter_versions", ["chapter_id"])


def downgrade() -> None:
    op.drop_index("ix_chapter_versions_chapter_id", "chapter_versions")
    op.drop_table("chapter_versions")
