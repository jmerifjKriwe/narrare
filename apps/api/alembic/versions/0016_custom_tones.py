"""Add custom_tones JSONB column to user_settings.

Stores user-defined writing tones as a JSON array. Each tone has
id, name, and instructions fields. Max 20 tones per user (enforced in service).

Revision ID: 0016_custom_tones
Revises: 0015_novel_writing_language
Create Date: 2026-05-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0016_custom_tones"
down_revision = "0015_novel_writing_language"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add custom_tones JSONB column with empty array default."""
    op.add_column(
        "user_settings",
        sa.Column(
            "custom_tones",
            JSONB(),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove custom_tones column."""
    op.drop_column("user_settings", "custom_tones")
