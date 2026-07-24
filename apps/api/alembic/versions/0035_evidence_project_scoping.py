"""Add novel_id column to invocation_evidence (ADR-070).

Project-scopes each evidence row so the Adaptivity Dashboard can list
per-novel adaptive snapshots (GET /api/v1/adaptive/{project_id}/snapshots).
Nullable + indexed for backward compatibility: pre-0035 rows keep NULL
novel_id and are simply absent from per-novel queries (they are
unattributable — the write path never captured the novel before this
migration).

Mirrors the nullable-column pattern of 0030_evidence_correlation.

Revision ID: 0035_evidence_project_scoping
Revises: 0034_evidence_adaptive_columns
Create Date: 2026-07-23 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0035_evidence_project_scoping"
down_revision: str | None = "0034_evidence_adaptive_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ADR-070: project-scope column for per-novel snapshot queries.
    op.add_column(
        "invocation_evidence",
        sa.Column("novel_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_invocation_evidence_novel_id",
        "invocation_evidence",
        ["novel_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invocation_evidence_novel_id",
        table_name="invocation_evidence",
    )
    op.drop_column("invocation_evidence", "novel_id")
