"""Initial schema — users, novels, chapters, volumes, settings

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgvector extension (needed for future embedding columns)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
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
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- novels ---
    op.create_table(
        "novels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("author", sa.String(200), nullable=False, server_default=""),
        sa.Column("genre", sa.String(100), nullable=False, server_default=""),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("tone", sa.String(100), nullable=False, server_default=""),
        sa.Column("story_structure", sa.String(100), nullable=False, server_default="three_act"),
        sa.Column("logline", sa.Text(), nullable=False, server_default=""),
        sa.Column("synopsis", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default="false"),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_novels_user_id", "novels", ["user_id"])

    # --- volumes ---
    op.create_table(
        "volumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("novel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_volumes_novel_id", "volumes", ["novel_id"])

    # --- chapters ---
    op.create_table(
        "chapters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("novel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("volume_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(500), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("pov_character_id", sa.String(100), nullable=False, server_default=""),
        sa.Column("timeline_position", sa.String(200), nullable=False, server_default=""),
        sa.Column("embeddings_dirty", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["volume_id"], ["volumes.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_chapters_novel_id", "chapters", ["novel_id"])
    op.create_index("ix_chapters_position", "chapters", ["position"])
    op.create_index("ix_chapters_volume_id", "chapters", ["volume_id"])

    # --- user_settings ---
    op.create_table(
        "user_settings",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("display_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("ui_language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("theme", sa.String(20), nullable=False, server_default="system"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- project_settings ---
    op.create_table(
        "project_settings",
        sa.Column(
            "novel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("novels.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("autosave_interval", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("default_language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("ai_provider", sa.String(50), nullable=False, server_default=""),
        sa.Column("ai_model", sa.String(200), nullable=False, server_default=""),
        sa.Column("model_overrides", sa.Text(), nullable=False, server_default="{}"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("project_settings")
    op.drop_table("user_settings")
    op.drop_index("ix_chapters_volume_id", "chapters")
    op.drop_index("ix_chapters_position", "chapters")
    op.drop_index("ix_chapters_novel_id", "chapters")
    op.drop_table("chapters")
    op.drop_index("ix_volumes_novel_id", "volumes")
    op.drop_table("volumes")
    op.drop_index("ix_novels_user_id", "novels")
    op.drop_table("novels")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
