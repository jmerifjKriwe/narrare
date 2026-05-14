"""Add AI settings tables and project override columns

Creates ``user_providers`` and ``user_ai_settings`` tables for
multi-provider AI configuration. Adds JSONB override columns to
``project_settings``. Migrates existing ``ai_provider``/``ai_model``
data from project_settings to the new structure.

Revision ID: 0004_ai_settings
Revises: 0003_widen_hashed_password
Create Date: 2026-05-13 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0004_ai_settings"
down_revision: str | None = "0003_widen_hashed_password"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Task 5.1: user_providers table
    # ------------------------------------------------------------------
    op.create_table(
        "user_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_name", sa.String(50), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "provider_name", name="uq_user_providers_user_name"),
    )
    op.create_index("ix_user_providers_user_id", "user_providers", ["user_id"])

    # ------------------------------------------------------------------
    # Task 5.2: user_ai_settings table
    # ------------------------------------------------------------------
    op.create_table(
        "user_ai_settings",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "default_provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_providers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "default_model",
            sa.String(200),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "category_overrides",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "intent_overrides",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "token_limit_profile",
            sa.String(20),
            nullable=False,
            server_default="balanced",
        ),
        sa.Column(
            "token_limit_overrides",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ------------------------------------------------------------------
    # Task 5.3: Add JSONB columns to project_settings
    # ------------------------------------------------------------------
    op.add_column(
        "project_settings",
        sa.Column(
            "category_overrides",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "project_settings",
        sa.Column(
            "intent_overrides",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "project_settings",
        sa.Column(
            "token_limit_overrides",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )

    # ------------------------------------------------------------------
    # Task 5.4: Data migration — move existing provider data
    # ------------------------------------------------------------------
    _migrate_existing_provider_data()


def _migrate_existing_provider_data() -> None:
    """Move project_settings.ai_provider / ai_model to user_providers + user_ai_settings.

    For each project_settings row where ai_provider is not empty:
    1. Look up the novel's user_id from the novels table.
    2. Insert into user_providers (api_key_encrypted = '' — user must re-enter).
    3. Insert/update user_ai_settings with the default_provider_id and default_model.

    Uses raw SQL via op.execute() for data migration within Alembic.
    """
    # Insert providers from project_settings, deduplicating per (user_id, provider_name).
    # Uses ON CONFLICT DO NOTHING because a user may own multiple novels with the same provider.
    op.execute(
        """
        INSERT INTO user_providers (
            id, user_id, provider_name, api_key_encrypted, base_url, is_active
        )
        SELECT
            gen_random_uuid(),
            n.user_id,
            ps.ai_provider,
            '',
            NULL,
            TRUE
        FROM project_settings ps
        JOIN novels n ON n.id = ps.novel_id
        WHERE ps.ai_provider != ''
        ON CONFLICT (user_id, provider_name) DO NOTHING
        """
    )

    # Set user_ai_settings for each user that now has a provider.
    # Pick the first (arbitrary) provider as default and use the model
    # from the first project that had this provider configured.
    op.execute(
        """
        INSERT INTO user_ai_settings (user_id, default_provider_id, default_model)
        SELECT
            up.user_id,
            up.id,
            COALESCE(
                (SELECT ps.ai_model
                 FROM project_settings ps
                 JOIN novels n ON n.id = ps.novel_id
                 WHERE n.user_id = up.user_id
                   AND ps.ai_provider = up.provider_name
                   AND ps.ai_model != ''
                 LIMIT 1),
                ''
            )
        FROM user_providers up
        WHERE up.is_active = TRUE
        ON CONFLICT (user_id) DO UPDATE SET
            default_provider_id = EXCLUDED.default_provider_id,
            default_model = EXCLUDED.default_model
        """
    )


def downgrade() -> None:
    # Remove JSONB columns from project_settings
    op.drop_column("project_settings", "token_limit_overrides")
    op.drop_column("project_settings", "intent_overrides")
    op.drop_column("project_settings", "category_overrides")

    # Drop new tables (order matters for FK)
    op.drop_table("user_ai_settings")
    op.drop_index("ix_user_providers_user_id", "user_providers")
    op.drop_table("user_providers")
