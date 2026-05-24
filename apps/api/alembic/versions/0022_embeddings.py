"""Add embeddings, context_usage_events tables and kb_entries enrichment.

Creates:
- ``embeddings`` table for generic vector storage with pgvector.
- ``context_usage_events`` for proactive suggestion feedback tracking.
- ``last_referenced_at`` and ``usage_count`` columns on ``kb_entries``.

HNSW index on ``embeddings.embedding`` for cosine similarity search.
B-tree index on ``embeddings(source_type, source_id)`` for source lookups.
B-tree indexes on ``context_usage_events`` for entry and novel queries.

pgvector extension is already enabled in migration 0001_initial.

Revision ID: 0022_embeddings
Revises: 0021_token_limits
Create Date: 2026-05-24 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0022_embeddings"
down_revision: str | None = "0021_token_limits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create embeddings tables and enrich kb_entries."""

    # --- embeddings ---
    # Uses op.execute() for raw SQL because the pgvector ``vector`` type
    # is not a standard SQLAlchemy column type and Alembic cannot render
    # it via op.create_table() without the pgvector Alembic render hook.
    op.execute(
        """
        CREATE TABLE embeddings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_type TEXT NOT NULL,
            source_id UUID NOT NULL,
            content_hash TEXT NOT NULL,
            embedding vector(1536) NOT NULL,
            model TEXT NOT NULL,
            dimension INT NOT NULL,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(source_type, source_id, model)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_embeddings_search ON embeddings USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute("CREATE INDEX idx_embeddings_source ON embeddings (source_type, source_id)")

    # --- context_usage_events ---
    op.create_table(
        "context_usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "novel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("novels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kb_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "action IN ('accepted', 'dismissed', 'pinned', 'unpinned')",
            name="ck_context_usage_events_action",
        ),
        sa.CheckConstraint(
            "source IN ('proactive', 'search', 'manual')",
            name="ck_context_usage_events_source",
        ),
    )
    op.create_index(
        "idx_usage_events_entry",
        "context_usage_events",
        ["entry_id"],
    )
    op.create_index(
        "idx_usage_events_novel",
        "context_usage_events",
        ["novel_id", sa.text("created_at DESC")],
    )

    # --- kb_entries enrichment ---
    op.add_column(
        "kb_entries",
        sa.Column("last_referenced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "kb_entries",
        sa.Column(
            "usage_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    """Drop embeddings tables and revert kb_entries enrichment."""
    # Revert kb_entries enrichment
    op.drop_column("kb_entries", "usage_count")
    op.drop_column("kb_entries", "last_referenced_at")

    # Drop context_usage_events
    op.drop_index("idx_usage_events_novel", "context_usage_events")
    op.drop_index("idx_usage_events_entry", "context_usage_events")
    op.drop_table("context_usage_events")

    # Drop embeddings (raw SQL because the table was created with raw SQL)
    op.execute("DROP INDEX IF EXISTS idx_embeddings_source")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_search")
    op.execute("DROP TABLE IF EXISTS embeddings")
