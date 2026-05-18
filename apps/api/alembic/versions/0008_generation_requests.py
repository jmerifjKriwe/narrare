"""Add generation_requests table and FK to chapter_versions.

Creates the generation_requests table for tracking AI chapter
generation jobs. Adds a nullable generation_request_id column
to chapter_versions to link a version to the request that
produced it.

Revision ID: 0008_generation_requests
Revises: 0007_volume_enrichment
Create Date: 2026-05-17 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0008_generation_requests"
down_revision: str | None = "0007_volume_enrichment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create generation_requests table and add FK to chapter_versions."""
    op.create_table(
        "generation_requests",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chapter_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("model_id", sa.String(100), nullable=True),
        sa.Column("provider_name", sa.String(50), nullable=True),
        sa.Column(
            "tokens_used",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "word_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "novel_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("novels.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
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
    )

    # Add nullable FK linking chapter_versions to the generation request
    op.add_column(
        "chapter_versions",
        sa.Column(
            "generation_request_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("generation_requests.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Drop generation_request_id from chapter_versions and drop table."""
    op.drop_column("chapter_versions", "generation_request_id")
    op.drop_table("generation_requests")
