"""Create wiki_summaries and wiki_chapter_summaries tables.

Creates:
- ``wiki_summaries`` — precomputed LLM-generated wiki for KB entities
- ``wiki_chapter_summaries`` — precomputed LLM-generated wiki for chapters

Revision ID: 0024_create_wiki_summaries
Revises: 0023_token_limit_migration
Create Date: 2026-05-29 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0024_create_wiki_summaries"
down_revision: str | None = "0023_token_limit_migration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create wiki_summaries and wiki_chapter_summaries tables."""
    # --- wiki_summaries ---
    op.create_table(
        "wiki_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "novel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("novels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kb_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("narrative_summary", sa.Text(), nullable=False),
        sa.Column("role_in_story", sa.Text(), nullable=True),
        sa.Column("key_attributes", postgresql.JSONB, nullable=True),
        sa.Column("relationships", postgresql.JSONB, nullable=True),
        sa.Column("chapter_references", postgresql.JSONB, nullable=True),
        sa.Column("character_arc", sa.Text(), nullable=True),
        sa.Column("depends_on", postgresql.JSONB, nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "content_hash",
            sa.String(64),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "refreshed_at",
            sa.DateTime(timezone=True),
            nullable=True,
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
            "status IN ('pending', 'fresh', 'stale')",
            name="ck_wiki_summaries_status",
        ),
        sa.UniqueConstraint("novel_id", "entity_id", name="uq_wiki_summary_entity"),
    )
    op.create_index("ix_wiki_summaries_status", "wiki_summaries", ["status"])
    op.create_index("ix_wiki_summaries_novel_id", "wiki_summaries", ["novel_id"])

    # --- wiki_chapter_summaries ---
    op.create_table(
        "wiki_chapter_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("narrative_summary", sa.Text(), nullable=False),
        sa.Column("key_events", postgresql.JSONB, nullable=True),
        sa.Column("entities_involved", postgresql.JSONB, nullable=True),
        sa.Column("themes", postgresql.JSONB, nullable=True),
        sa.Column("emotional_arc", sa.Text(), nullable=True),
        sa.Column(
            "chapter_content_hash",
            sa.String(64),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "wiki_prompt_version",
            sa.String(20),
            nullable=False,
            server_default="1.0.0",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
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
            "status IN ('pending', 'fresh', 'stale')",
            name="ck_wiki_chapter_status",
        ),
    )
    op.create_index("ix_wiki_chapter_status", "wiki_chapter_summaries", ["status"])
    op.create_index(
        "ix_wiki_chapter_chapter_id",
        "wiki_chapter_summaries",
        ["chapter_id"],
    )


def downgrade() -> None:
    """Drop wiki_chapter_summaries and wiki_summaries tables."""
    op.drop_index("ix_wiki_chapter_chapter_id", "wiki_chapter_summaries")
    op.drop_index("ix_wiki_chapter_status", "wiki_chapter_summaries")
    op.drop_table("wiki_chapter_summaries")
    op.drop_index("ix_wiki_summaries_novel_id", "wiki_summaries")
    op.drop_index("ix_wiki_summaries_status", "wiki_summaries")
    op.drop_table("wiki_summaries")
