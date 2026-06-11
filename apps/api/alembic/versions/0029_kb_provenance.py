"""Add source and review_status columns to kb_entries.

Adds provenance tracking so auto-extracted KB entries can be distinguished
from manually created ones.  ``source`` records the origin (e.g. "manual",
"auto_extraction"), and ``review_status`` tracks the review state of
auto-extracted entries (approved / pending / rejected).

Both columns are NOT NULL with server defaults so existing rows get
"manual" / "approved" respectively — matching pre-migration behaviour.

Revision ID: 0029_kb_provenance
Revises: 0028_invocation_evidence
Create Date: 2026-06-10 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0029_kb_provenance"
down_revision: str | None = "0028_invocation_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "kb_entries",
        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            server_default="manual",
        ),
    )
    op.add_column(
        "kb_entries",
        sa.Column(
            "review_status",
            sa.String(20),
            nullable=False,
            server_default="approved",
        ),
    )
    op.execute(
        "ALTER TABLE kb_entries ADD CONSTRAINT ck_kb_entries_review_status "
        "CHECK (review_status IN ('approved', 'pending', 'rejected'))",
    )


def downgrade() -> None:
    op.drop_constraint("ck_kb_entries_review_status", "kb_entries", type_="check")
    op.drop_column("kb_entries", "review_status")
    op.drop_column("kb_entries", "source")
