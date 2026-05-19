"""Add KB entries and relationships tables.

Creates:
- ``kb_entries`` for entity instances with JSONB metadata.
- ``kb_relationships`` for directed/mutual edges between entries.
- GIN index on ``kb_entries.metadata`` for JSON queries.

Revision ID: 0009_kb_entries_relationships
Revises: 0008_generation_requests
Create Date: 2026-05-18 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0009_kb_entries_relationships"
down_revision: str | None = "0008_generation_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create kb_entries and kb_relationships tables."""
    # --- kb_entries ---
    op.create_table(
        "kb_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "novel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("novels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(500), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("tags", postgresql.JSONB, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column(
            "body",
            sa.Text(),
            nullable=True,
            server_default="",
        ),
        sa.Column("template_version", sa.String(20), nullable=True),
        sa.Column(
            "embeddings_dirty",
            sa.Boolean(),
            nullable=False,
            server_default="false",
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
            name="ck_kb_entries_entity_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'reviewed', 'canon', 'deprecated')",
            name="ck_kb_entries_status",
        ),
        sa.UniqueConstraint("novel_id", "slug", name="uq_kb_entries_novel_slug"),
    )
    op.create_index("ix_kb_entries_entity_type", "kb_entries", ["entity_type"])
    op.create_index("ix_kb_entries_novel_id", "kb_entries", ["novel_id"])
    op.create_index("ix_kb_entries_novel_type", "kb_entries", ["novel_id", "entity_type"])
    # GIN index for JSONB metadata queries
    op.execute("CREATE INDEX ix_kb_entries_metadata_gin ON kb_entries USING gin (metadata)")

    # --- kb_relationships ---
    op.create_table(
        "kb_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kb_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kb_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rel_type", sa.String(50), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column(
            "direction",
            sa.String(10),
            nullable=False,
            server_default="directed",
        ),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
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
            "source_id != target_id",
            name="ck_kb_relationships_no_self_ref",
        ),
        sa.CheckConstraint(
            "direction IN ('directed', 'mutual')",
            name="ck_kb_relationships_direction",
        ),
        sa.UniqueConstraint(
            "source_id",
            "target_id",
            "rel_type",
            name="uq_kb_relationships_unique",
        ),
    )
    op.create_index("ix_kb_relationships_source_id", "kb_relationships", ["source_id"])
    op.create_index("ix_kb_relationships_target_id", "kb_relationships", ["target_id"])


def downgrade() -> None:
    """Drop kb_relationships and kb_entries tables."""
    op.drop_index("ix_kb_relationships_target_id", "kb_relationships")
    op.drop_index("ix_kb_relationships_source_id", "kb_relationships")
    op.drop_table("kb_relationships")
    op.execute("DROP INDEX IF EXISTS ix_kb_entries_metadata_gin")
    op.drop_index("ix_kb_entries_novel_type", "kb_entries")
    op.drop_index("ix_kb_entries_novel_id", "kb_entries")
    op.drop_index("ix_kb_entries_entity_type", "kb_entries")
    op.drop_table("kb_entries")
