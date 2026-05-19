"""Add kb_templates table for template overrides.

Creates the ``kb_templates`` table that stores user, project, and global
template overrides with full content (YAML frontmatter + body markdown).

Revision ID: 0010_kb_templates
Revises: 0009_kb_entries_relationships
Create Date: 2026-05-19 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0010_kb_templates"
down_revision: str | None = "0009_kb_entries_relationships"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create kb_templates table for template overrides."""
    # Create the enum type first
    op.execute("CREATE TYPE templatescope AS ENUM ('user', 'project', 'global')")

    op.create_table(
        "kb_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column(
            "scope",
            sa.Enum("user", "project", "global", name="templatescope", create_type=False),
            nullable=False,
        ),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("based_on_version", sa.String(20), nullable=True),
        sa.Column(
            "schema_version",
            sa.String(20),
            nullable=False,
            server_default="2.0.0",
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
        sa.CheckConstraint(
            "entity_type IN ('character', 'location', 'faction', 'object', 'system', 'timeline')",
            name="ck_kb_templates_entity_type",
        ),
        sa.UniqueConstraint(
            "entity_type",
            "language",
            "scope",
            "scope_id",
            name="uq_kb_templates_unique",
        ),
    )
    op.create_index("ix_kb_templates_scope", "kb_templates", ["scope", "scope_id"])


def downgrade() -> None:
    """Drop kb_templates table and cleanup."""
    op.drop_index("ix_kb_templates_scope", "kb_templates")
    op.drop_table("kb_templates")
    op.execute("DROP TYPE IF EXISTS templatescope")
