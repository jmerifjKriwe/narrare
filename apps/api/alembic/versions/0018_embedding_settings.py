"""Add embedding columns to user_ai_settings table.

Adds embedding_provider and embedding_model columns so users can
configure which embedding model is used for semantic operations.

Revision ID: 0018_embedding_settings
Revises: 0017_feedback_rating
Create Date: 2026-05-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0018_embedding_settings"
down_revision = "0017_feedback_rating"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add embedding_provider and embedding_model columns."""
    op.add_column(
        "user_ai_settings",
        sa.Column(
            "embedding_provider",
            sa.String(20),
            nullable=False,
            server_default="auto",
        ),
    )
    op.add_column(
        "user_ai_settings",
        sa.Column(
            "embedding_model",
            sa.String(100),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove embedding columns."""
    op.drop_column("user_ai_settings", "embedding_model")
    op.drop_column("user_ai_settings", "embedding_provider")
