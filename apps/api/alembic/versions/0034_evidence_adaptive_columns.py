"""Add adaptive_source_summary + adaptive_weights JSONB columns (ADR-069 D11).

Stores the adaptive-context provenance summary and the resolved weight set
on each invocation_evidence row, so adoption audits can reconstruct which
adaptive inputs shaped a prompt and which weights were in effect.

Both columns are nullable for backward compatibility with pre-ADR-069 rows:
the AdaptiveContextProviderImpl falls back to defaults when NULL
(graceful degradation per RULE-11).

Mirrors the JSONB pattern of validation_errors on the same table.

Revision ID: 0034_evidence_adaptive_columns
Revises: 0033_adaptive_settings_column
Create Date: 2026-07-21 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0034_evidence_adaptive_columns"
down_revision: str | None = "0033_adaptive_settings_column"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ADR-069 D11: adaptive context provenance + resolved weights.
    op.add_column(
        "invocation_evidence",
        sa.Column(
            "adaptive_source_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "invocation_evidence",
        sa.Column(
            "adaptive_weights",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("invocation_evidence", "adaptive_weights")
    op.drop_column("invocation_evidence", "adaptive_source_summary")
