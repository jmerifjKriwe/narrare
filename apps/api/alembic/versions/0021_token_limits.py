"""Add user_token_limits and project_token_limits tables.

Separate tables for per-user and per-project token limit overrides.
Each stores overrides as a single JSONB column (no fixed schema).

Revision ID: 0021_token_limits
Revises: 0020_generation_tone_column
Create Date: 2026-05-24 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0021_token_limits"
down_revision: str | None = "0020_generation_tone_column"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create user_token_limits and project_token_limits tables."""
    op.create_table(
        "user_token_limits",
        sa.Column("user_id", sa.String(), primary_key=True),
        sa.Column(
            "overrides",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_table(
        "project_token_limits",
        sa.Column("project_id", sa.String(), primary_key=True),
        sa.Column(
            "overrides",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    """Drop user_token_limits and project_token_limits tables."""
    op.drop_table("user_token_limits")
    op.drop_table("project_token_limits")
