"""Add prompt_revisions table for prompt override history (CR-AUFG-07-19).

Creates the DB-backed, append-only ``prompt_revisions`` table.  The active
override remains a FILE (cascade source of truth, owned by core
``PromptManagementService``); this table is a secondary, non-authoritative
record keyed by the logical identity ``(prompt_id, scope)``.

RULE-08: core stays infra-free, so the model lives in the backend layer and
this migration is the only place that owns the ``prompt_revisions`` DDL.

Revision ID: 0031_prompt_revisions
Revises: 0030_evidence_correlation
Create Date: 2026-06-23 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0031_prompt_revisions"
down_revision: str | None = "0030_evidence_correlation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_revisions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("prompt_id", sa.String(200), nullable=False),
        sa.Column(
            "scope",
            sa.String(10),
            nullable=False,
            server_default="project",
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("change_reason", sa.String(200), nullable=True),
        sa.Column(
            "restored_from_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prompt_revisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Composite index supporting the history list query:
    #   WHERE prompt_id=? AND scope=? ORDER BY created_at DESC
    op.create_index(
        "ix_prompt_revisions_prompt_scope_created",
        "prompt_revisions",
        ["prompt_id", "scope", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_prompt_revisions_prompt_scope_created",
        table_name="prompt_revisions",
    )
    op.drop_table("prompt_revisions")
