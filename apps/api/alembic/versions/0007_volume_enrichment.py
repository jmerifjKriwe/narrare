"""Add enrichment columns to volumes table.

Adds subtitle, description, word_count_target, and is_default columns
to the volumes table. These support volume metadata and the default-volume
concept used when creating novels.

Revision ID: 0007_volume_enrichment
Revises: 0006_feedback_events
Create Date: 2026-05-17 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0007_volume_enrichment"
down_revision: str | None = "0006_feedback_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add subtitle, description, word_count_target, is_default to volumes."""
    op.add_column("volumes", sa.Column("subtitle", sa.String(500), nullable=True))
    op.add_column("volumes", sa.Column("description", sa.Text, nullable=True))
    op.add_column("volumes", sa.Column("word_count_target", sa.Integer(), nullable=True))
    op.add_column(
        "volumes",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    """Drop enrichment columns from volumes."""
    op.drop_column("volumes", "is_default")
    op.drop_column("volumes", "word_count_target")
    op.drop_column("volumes", "description")
    op.drop_column("volumes", "subtitle")
