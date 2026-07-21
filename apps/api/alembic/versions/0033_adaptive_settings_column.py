"""Add adaptive_settings JSONB column to project_settings (ADR-069 Decision 2).

Stores the per-project AdaptiveSettings (enabled flag + AdaptiveWeights) as
JSONB. NULL for existing rows — the AdaptiveContextProviderImpl falls back
to defaults when no row is present yet (graceful degradation per RULE-11).

Mirrors the existing category_overrides / intent_overrides / token_limit_overrides
JSONB pattern on the same table (Decision 2 Option β — extend, don't add a
parallel table).

Revision ID: 0033_adaptive_settings_column
Revises: 0032_dismissed_findings
Create Date: 2026-07-20 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0033_adaptive_settings_column"
down_revision: str | None = "0032_dismissed_findings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_settings",
        sa.Column(
            "adaptive_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("project_settings", "adaptive_settings")
