"""Migrate old token_limit_overrides/token_limit_profile to new tables.

Phase 1 of SET-005 data migration: copies data from old columns
(user_ai_settings.token_limit_profile + token_limit_overrides and
project_settings.token_limit_profile + token_limit_overrides) into
the new tables (user_token_limits and project_token_limits).

Non-destructive — old columns keep their data for backward compat.
Idempotent — WHERE NOT EXISTS prevents overwriting existing new data.

Revision ID: 0023_token_limit_migration
Revises: 0022_embeddings
Create Date: 2026-05-26 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0023_token_limit_migration"
down_revision: str | None = "0022_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Migrate old token limit columns to new tables.

    Two-phase approach:
    1. Copy user-level data from user_ai_settings to user_token_limits
    2. Copy project-level data from project_settings to project_token_limits

    Uses WHERE NOT EXISTS for idempotency — rows that already exist
    in the new tables are not overwritten.

    Maps profile names to output limits:
      quick      →  500
      balanced   → 2000
      long_texts → 8000
      other      → 4096
    """
    # Phase A: Migrate user token limits
    # Only migrates rows with non-default settings (non-empty overrides
    # or non-balanced profile) that don't already exist in new table.
    op.execute(
        sa.text(
            """
            INSERT INTO user_token_limits (user_id, overrides)
            SELECT
                uas.user_id::text,
                jsonb_build_object(
                    'token_profile', COALESCE(uas.token_limit_profile, 'balanced'),
                    'output_limit',
                        CASE COALESCE(uas.token_limit_profile, 'balanced')
                            WHEN 'quick' THEN 500
                            WHEN 'balanced' THEN 2000
                            WHEN 'long_texts' THEN 8000
                            ELSE 4096
                        END,
                    'legacy_per_category_overrides',
                        COALESCE(uas.token_limit_overrides, '{}'::jsonb)
                )
            FROM user_ai_settings uas
            WHERE NOT EXISTS (
                SELECT 1 FROM user_token_limits utl
                WHERE utl.user_id = uas.user_id::text
            )
            AND (
                uas.token_limit_overrides IS NOT NULL
                AND uas.token_limit_overrides != '{}'::jsonb
                OR uas.token_limit_profile != 'balanced'
            )
            """
        )
    )

    # Phase B: Migrate project token limits
    op.execute(
        sa.text(
            """
            INSERT INTO project_token_limits (project_id, overrides)
            SELECT
                ps.novel_id::text,
                jsonb_build_object(
                    'token_profile', COALESCE(ps.token_limit_profile, 'balanced'),
                    'output_limit',
                        CASE COALESCE(ps.token_limit_profile, 'balanced')
                            WHEN 'quick' THEN 500
                            WHEN 'balanced' THEN 2000
                            WHEN 'long_texts' THEN 8000
                            ELSE 4096
                        END,
                    'legacy_per_category_overrides',
                        COALESCE(ps.token_limit_overrides, '{}'::jsonb)
                )
            FROM project_settings ps
            WHERE NOT EXISTS (
                SELECT 1 FROM project_token_limits ptl
                WHERE ptl.project_id = ps.novel_id::text
            )
            AND (
                ps.token_limit_overrides IS NOT NULL
                AND ps.token_limit_overrides != '{}'::jsonb
                OR ps.token_limit_profile != 'balanced'
            )
            """
        )
    )


def downgrade() -> None:
    """Reverse migration — remove rows created by upgrade.

    No data loss on downgrade: old columns still have their original data.
    Only deletes rows that have a matching user/project in the old tables.
    """
    op.execute(
        sa.text(
            """
            DELETE FROM user_token_limits utl
            WHERE EXISTS (
                SELECT 1 FROM user_ai_settings uas
                WHERE uas.user_id::text = utl.user_id
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM project_token_limits ptl
            WHERE EXISTS (
                SELECT 1 FROM project_settings ps
                WHERE ps.novel_id::text = ptl.project_id
            )
            """
        )
    )
