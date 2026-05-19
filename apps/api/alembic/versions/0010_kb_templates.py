"""Add kb_templates table for template overrides.

Creates the ``kb_templates`` table that stores user, project, and global
template overrides with full content (YAML frontmatter + body markdown).

Revision ID: 0010_kb_templates
Revises: 0009_kb_entries_relationships
Create Date: 2026-05-19 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0010_kb_templates"
down_revision: str | None = "0009_kb_entries_relationships"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create kb_templates table for template overrides."""
    # Create the enum type (idempotent — safe to re-run)
    op.execute(
        "DO $$ BEGIN"
        "  CREATE TYPE templatescope AS ENUM ('user', 'project', 'global');"
        " EXCEPTION WHEN duplicate_object THEN NULL;"
        " END $$"
    )

    # Create table (use raw SQL for idempotency — table may partially exist)
    op.execute(
        "CREATE TABLE IF NOT EXISTS kb_templates ("
        "  id UUID PRIMARY KEY,"
        "  entity_type VARCHAR(50) NOT NULL,"
        "  language VARCHAR(10) NOT NULL DEFAULT 'en',"
        "  scope templatescope NOT NULL,"
        "  scope_id UUID,"
        "  content TEXT NOT NULL,"
        "  based_on_version VARCHAR(20),"
        "  schema_version VARCHAR(20) NOT NULL DEFAULT '2.0.0',"
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
        "  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
        "  CONSTRAINT ck_kb_templates_entity_type"
        "    CHECK (entity_type IN ("
        "      'character','location','faction',"
        "      'object','system','timeline'"
        "    )),"
        "  CONSTRAINT uq_kb_templates_unique"
        "    UNIQUE (entity_type, language, scope, scope_id)"
        ")"
    )

    # Create index (idempotent)
    op.execute("CREATE INDEX IF NOT EXISTS ix_kb_templates_scope ON kb_templates (scope, scope_id)")


def downgrade() -> None:
    """Drop kb_templates table and cleanup."""
    op.drop_index("ix_kb_templates_scope", "kb_templates")
    op.drop_table("kb_templates")
    op.execute("DROP TYPE IF EXISTS templatescope")
