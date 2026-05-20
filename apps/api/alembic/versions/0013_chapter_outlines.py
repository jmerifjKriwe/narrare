"""Create chapter_outlines table for storyboard feature.

Stores per-chapter outline data: stage assignment within the chosen
story structure, planned beats (JSONB), and free-form outline notes.

Idempotent — uses ``IF NOT EXISTS`` / ``IF NOT EXISTS`` patterns.

RULE-14: Cross-table check — verifies ``chapters`` and
``chapter_versions`` tables exist before creating FK references.

Revision ID: 0013_chapter_outlines
Revises: 0012_drop_template_language
Create Date: 2026-05-19 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0013_chapter_outlines"
down_revision: str | None = "0012_drop_template_language"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create chapter_outlines table."""
    # RULE-14: Cross-table existence check
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'chapters'
            ) THEN
                RAISE EXCEPTION 'Prerequisite table "chapters" does not exist';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'chapter_versions'
            ) THEN
                RAISE EXCEPTION 'Prerequisite table "chapter_versions" does not exist';
            END IF;
        END;
        $$
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS chapter_outlines (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chapter_id UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
            version_id UUID REFERENCES chapter_versions(id) ON DELETE SET NULL,
            stage_assignment VARCHAR(50) NOT NULL DEFAULT '',
            planned_beats JSONB DEFAULT '[]'::jsonb,
            outline_notes TEXT DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(chapter_id)
        )
        """
    )

    # Index for looking up outlines by chapter
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chapter_outlines_chapter_id ON chapter_outlines (chapter_id)"
    )


def downgrade() -> None:
    """Drop chapter_outlines table."""
    op.execute("DROP INDEX IF EXISTS ix_chapter_outlines_chapter_id")
    op.execute("DROP TABLE IF EXISTS chapter_outlines")
