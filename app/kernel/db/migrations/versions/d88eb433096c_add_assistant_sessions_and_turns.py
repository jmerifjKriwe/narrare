"""add assistant sessions and turns

The entity interview's storage (design: assistant sessions, W9): one session per
conversation with the model, one turn per transcript line. ``assistant_sessions``
hangs off the novel and carries the mode, the interview's subject when it has
one, and the dialog's draft proposal as JSONB; ``assistant_turns`` hangs off the
session, numbered by ``seq``, unique per session. Both tables carry their own
``user_id`` (rule 4) and both foreign keys cascade — a deleted novel takes its
interviews and their turns with it.

The models carry the same tables in the same commit (``AssistantSession``,
``AssistantTurn``), so the models-vs-history gate stays equal.

Revision ID: d88eb433096c
Revises: 9e4b21c7af50
Create Date: 2026-11-24 12:00:00.000000

"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]
from sqlalchemy.dialects import postgresql

revision: str = "d88eb433096c"
down_revision: str | Sequence[str] | None = "9e4b21c7af50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assistant_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("proposal", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["novel_id"],
            ["novels.id"],
            name=op.f("fk_assistant_sessions_novel_id_novels"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_assistant_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_sessions")),
    )
    op.create_index(
        op.f("ix_assistant_sessions_novel_id"), "assistant_sessions", ["novel_id"], unique=False
    )
    op.create_index(
        op.f("ix_assistant_sessions_user_id"), "assistant_sessions", ["user_id"], unique=False
    )

    op.create_table(
        "assistant_turns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("act", sa.String(length=32), nullable=True),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("suggestion_state", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["assistant_sessions.id"],
            name=op.f("fk_assistant_turns_session_id_assistant_sessions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_assistant_turns_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_turns")),
        sa.UniqueConstraint("session_id", "seq", name="uq_assistant_turns_seq"),
    )
    op.create_index(
        op.f("ix_assistant_turns_session_id"), "assistant_turns", ["session_id"], unique=False
    )
    op.create_index(
        op.f("ix_assistant_turns_user_id"), "assistant_turns", ["user_id"], unique=False
    )


def downgrade() -> None:
    # The child first: its foreign key points at the session table.
    op.drop_index(op.f("ix_assistant_turns_user_id"), table_name="assistant_turns")
    op.drop_index(op.f("ix_assistant_turns_session_id"), table_name="assistant_turns")
    op.drop_table("assistant_turns")
    op.drop_index(op.f("ix_assistant_sessions_user_id"), table_name="assistant_sessions")
    op.drop_index(op.f("ix_assistant_sessions_novel_id"), table_name="assistant_sessions")
    op.drop_table("assistant_sessions")
