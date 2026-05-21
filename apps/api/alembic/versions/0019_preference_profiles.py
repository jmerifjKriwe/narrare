"""Create preference_profiles table.

Stores derived user preference profiles per project, including style,
content, and avoidance patterns extracted from feedback events.

Revision ID: 0019_preference_profiles
Revises: 0018_embedding_settings
Create Date: 2026-05-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0019_preference_profiles"
down_revision = "0018_embedding_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create preference_profiles table with composite unique constraint."""
    op.create_table(
        "preference_profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "style_patterns",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "content_patterns",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "avoidance_patterns",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            server_default="0.0",
        ),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "event_count_at_analysis",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id",
            "project_id",
            name="uq_preference_profiles_user_project",
        ),
    )


def downgrade() -> None:
    """Drop preference_profiles table."""
    op.drop_table("preference_profiles")
