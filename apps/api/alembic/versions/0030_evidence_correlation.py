"""Add ADR-045 correlation columns to invocation_evidence.

Adds invocation correlation fields so evidence records can be joined
across prepare → finalize → model-call stages for a single invocation.
All columns are nullable for backward compatibility with pre-ADR-045 rows.

Privacy guarantee: These columns store UUIDs, salted hashes, counts, and
status strings only — no raw prompt text or user prose (ADR-045 §2).

Revision ID: 0030_evidence_correlation
Revises: 0029_kb_provenance
Create Date: 2026-06-13 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0030_evidence_correlation"
down_revision: str | None = "0029_kb_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ADR-045 §2: correlation fields
    op.add_column(
        "invocation_evidence",
        sa.Column("invocation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "invocation_evidence",
        sa.Column("prepared_context_fingerprint", sa.String(128), nullable=True),
    )
    op.add_column(
        "invocation_evidence",
        sa.Column("prompt_fingerprint", sa.String(128), nullable=True),
    )
    op.add_column(
        "invocation_evidence",
        sa.Column("budget_decision_fingerprint", sa.String(128), nullable=True),
    )
    op.add_column(
        "invocation_evidence",
        sa.Column("model_call_marker", sa.String(200), nullable=True),
    )
    op.add_column(
        "invocation_evidence",
        sa.Column("manual_injection_exception", sa.String(200), nullable=True),
    )

    # Index invocation_id for correlation joins
    op.create_index(
        "ix_invocation_evidence_invocation_id",
        "invocation_evidence",
        ["invocation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invocation_evidence_invocation_id",
        table_name="invocation_evidence",
    )
    op.drop_column("invocation_evidence", "manual_injection_exception")
    op.drop_column("invocation_evidence", "model_call_marker")
    op.drop_column("invocation_evidence", "budget_decision_fingerprint")
    op.drop_column("invocation_evidence", "prompt_fingerprint")
    op.drop_column("invocation_evidence", "prepared_context_fingerprint")
    op.drop_column("invocation_evidence", "invocation_id")
