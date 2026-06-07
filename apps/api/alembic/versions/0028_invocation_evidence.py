"""Add invocation_evidence table for persistent evidence store (ADR-042).

Creates the PostgreSQL-backed evidence table for AI invocation adoption
records. Supports adoption scoring, quality metrics, and audit report
queries with appropriate indices.

Privacy guarantee (ADR-038): Schema contains zero prompt text, zero user
prose, and zero eval case content — only identifiers, statuses, booleans,
and structured metadata.

Revision ID: 0028_invocation_evidence
Revises: 0027_timeline_events
Create Date: 2026-06-07 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0028_invocation_evidence"
down_revision: str | None = "0027_timeline_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invocation_evidence",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "feature_id",
            sa.String(50),
            nullable=False,
        ),
        sa.Column("intent", sa.String(50), nullable=False),
        sa.Column("mode", sa.String(50), nullable=True),
        sa.Column("language", sa.String(5), server_default="en", nullable=False),
        sa.Column("streaming", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("preference_status", sa.String(20), nullable=False),
        sa.Column("kb_suggested_status", sa.String(20), nullable=False),
        sa.Column("voice_profile_status", sa.String(20), nullable=True),
        sa.Column("output_budget_profile", sa.String(50), nullable=True),
        sa.Column("final_prompt_validated", sa.Boolean(), nullable=False),
        sa.Column(
            "validation_errors",
            postgresql.JSONB(),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("audit_state", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("prompt_route", sa.String(200), nullable=False),
    )

    # Indexes
    op.create_index(
        "ix_invocation_evidence_feature_mode",
        "invocation_evidence",
        ["feature_id", "mode"],
    )
    op.create_index(
        "ix_invocation_evidence_created_at",
        "invocation_evidence",
        ["created_at"],
    )
    op.create_index(
        "ix_invocation_evidence_audit_state",
        "invocation_evidence",
        ["audit_state"],
    )
    op.create_index(
        "ix_invocation_evidence_intent",
        "invocation_evidence",
        ["intent"],
    )


def downgrade() -> None:
    op.drop_table("invocation_evidence")
