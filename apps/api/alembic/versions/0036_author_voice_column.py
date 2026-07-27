"""Add author_voice JSONB column to project_settings (ADR-074 / ANAL-007).

Stores the per-novel ``AuthorVoiceProfile`` (descriptive + metric groups) as
JSONB. NULL for existing rows — consumers degrade gracefully ("no profile";
RULE-11): generation renders empty ``{{author_voice}}`` and the future Phase 2B
author-drift checker skips. Re-analysis overwrites the stored profile (YAGNI:
no historical versioning in v1).

Mirrors the ``adaptive_settings`` column added by migration 0033 (ADR-069
Decision 2) — the established pattern for a per-novel structured JSONB column
on ``ProjectSettings``. Author voice is novel-scoped (one profile per novel,
keyed by ``ProjectSettings.novel_id``); there is no series entity today.

RULE-14: this migration lands in the SAME task as the ``ProjectSettings``
model change (``author_voice`` column). A model change without a migration is
a build failure.

See:
    ADR-074 — Author Voice Storage Contract (the storage contract this migrates).
    ADR-069 — AdaptiveSettings pattern (the structural parallel mirrored here).
    migration 0033_adaptive_settings_column — the reference implementation.

Revision ID: 0036_author_voice_column
Revises: 0035_evidence_project_scoping
Create Date: 2026-07-27 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0036_author_voice_column"
down_revision: str | None = "0035_evidence_project_scoping"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_settings",
        sa.Column(
            "author_voice",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("project_settings", "author_voice")
