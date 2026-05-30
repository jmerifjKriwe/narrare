"""Create chat_conversations and chat_messages tables.

Creates:
- ``chat_conversations`` — chat conversations scoped to a project and user
- ``chat_messages`` — individual messages within a chat conversation

Revision ID: 0025_create_chat_tables
Revises: 0024_create_wiki_summaries
Create Date: 2026-05-30 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0025_create_chat_tables"
down_revision: str | None = "0024_create_wiki_summaries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create chat_conversations and chat_messages tables."""
    # --- chat_conversations ---
    op.create_table(
        "chat_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("novels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=True),
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
    op.create_index("ix_chat_conversations_project_id", "chat_conversations", ["project_id"])
    op.create_index("ix_chat_conversations_user_id", "chat_conversations", ["user_id"])

    # --- chat_messages ---
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])


def downgrade() -> None:
    """Drop chat_messages and chat_conversations tables."""
    op.drop_index("ix_chat_messages_conversation_id", "chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_conversations_user_id", "chat_conversations")
    op.drop_index("ix_chat_conversations_project_id", "chat_conversations")
    op.drop_table("chat_conversations")
