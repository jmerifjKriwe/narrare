"""Add dismissed_findings table for consistency finding dismissal (CR-AUFG-07-26).

Creates a table storing user-dismissed consistency findings, keyed by a
stable fingerprint (``description::entity_names``) per novel.  This lets
users permanently ignore findings they have reviewed and consciously
accepted, so re-running a consistency check no longer resurfaces them.

Revision ID: 0032_dismissed_findings
Revises: 0031_prompt_revisions
Create Date: 2026-07-14 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0032_dismissed_findings"
down_revision: str | None = "0031_prompt_revisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dismissed_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "novel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("novels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(512), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "dismissed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "novel_id",
            "fingerprint",
            name="uq_dismissed_novel_fingerprint",
        ),
    )
    op.create_index(
        "ix_dismissed_findings_novel_id",
        "dismissed_findings",
        ["novel_id"],
    )


def downgrade() -> None:
    op.drop_table("dismissed_findings")
