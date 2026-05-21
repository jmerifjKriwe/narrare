"""Add tone column to generation_requests table.

Stores the selected writing tone for each generation request so it can
be retrieved during streaming. Defaults to 'balanced' for existing rows.

Revision ID: 0020_generation_tone_column
Revises: 0019_preference_profiles
Create Date: 2026-05-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0020_generation_tone_column"
down_revision = "0019_preference_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add tone VARCHAR(100) NOT NULL DEFAULT 'balanced'."""
    op.add_column(
        "generation_requests",
        sa.Column(
            "tone",
            sa.String(100),
            nullable=False,
            server_default="balanced",
        ),
    )


def downgrade() -> None:
    """Remove tone column."""
    op.drop_column("generation_requests", "tone")
