"""Add partial unique index on generation_requests for active chapter.

Ensures at most one row per chapter_id can have status ``pending`` or
``streaming`` at the database level.  This is the defence-in-depth guard
against the TOCTOU race described in finding
``fnd_sig-feat-library-000e72e7f6-06b7_9562565477``.

The application-level fix uses ``SELECT ... FOR UPDATE`` in
``GenerationRepository.create_if_no_active()``; this index catches any
remaining edge cases.

Revision ID: 0026_active_generation_unique
Revises: 0025_create_chat_tables
Create Date: 2026-06-01 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0026_active_generation_unique"
down_revision: str | None = "0025_create_chat_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX uq_generation_requests_active_chapter
        ON generation_requests (chapter_id)
        WHERE status IN ('pending', 'streaming')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS uq_generation_requests_active_chapter
        """
    )
