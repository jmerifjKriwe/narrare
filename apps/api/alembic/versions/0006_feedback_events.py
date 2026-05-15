"""Add feedback_events table for memory subsystem.

Creates the feedback_events table used to persist user feedback on AI
suggestions. Each row captures what the user did with a suggestion
(accept, reject, modify), along with context for preference derivation.

Includes a composite index on (user_id, project_id) for efficient
lookup by user/project scope.

Revision ID: 0006_feedback_events
Revises: 0005_project_settings
Create Date: 2026-05-15 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0006_feedback_events"
down_revision: str | None = "0005_project_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create feedback_events table with composite index."""
    op.create_table(
        "feedback_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "suggestion_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("intent", sa.String(50), nullable=False),
        sa.Column("suggestion_text", sa.Text, nullable=False),
        sa.Column("modification", sa.Text, nullable=True),
        sa.Column("context", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_feedback_events_user_project",
        "feedback_events",
        ["user_id", "project_id"],
    )


def downgrade() -> None:
    """Drop feedback_events table."""
    op.drop_index("ix_feedback_events_user_project", table_name="feedback_events")
    op.drop_table("feedback_events")
