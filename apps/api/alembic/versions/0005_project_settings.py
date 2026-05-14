"""Add token_limit_profile column to project_settings.

The column was defined in the SQLAlchemy model (``ProjectSettings.token_limit_profile``)
but was missed in migration 0004_ai_settings which only added it to ``user_ai_settings``.
The setup wizard crashes on completion because the INSERT includes the missing column.

Revision ID: 0005_project_settings
Revises: 0004_ai_settings
Create Date: 2026-05-14 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0005_project_settings"
down_revision: str | None = "0004_ai_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add token_limit_profile column to project_settings table."""
    op.add_column(
        "project_settings",
        sa.Column(
            "token_limit_profile",
            sa.String(20),
            nullable=False,
            server_default="balanced",
        ),
    )


def downgrade() -> None:
    """Remove token_limit_profile column from project_settings table."""
    op.drop_column("project_settings", "token_limit_profile")
