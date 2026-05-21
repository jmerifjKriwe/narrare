"""Create graph_runs table for WritingGraph state persistence.

Stores serialized WritingState checkpoints during graph execution.
Supports resume/restore of interrupted graph runs.

Revision ID: 0014_graph_runs
Revises: 0013_chapter_outlines
Create Date: 2026-05-21 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0014_graph_runs"
down_revision: str | None = "0013_chapter_outlines"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create graph_runs table.

    ``chapter_id`` is nullable because graph runs can start before
    a chapter is assigned (e.g. during outlining phase).
    """
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS graph_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id VARCHAR(64) NOT NULL UNIQUE,
            chapter_id UUID REFERENCES chapters(id) ON DELETE CASCADE,
            checkpoint_data JSONB NOT NULL DEFAULT '{}'::jsonb,
            status VARCHAR(32) NOT NULL DEFAULT 'running',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_graph_runs_run_id ON graph_runs (run_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_graph_runs_chapter_id ON graph_runs (chapter_id)")


def downgrade() -> None:
    """Drop graph_runs table and its indexes."""
    op.execute("DROP INDEX IF EXISTS ix_graph_runs_chapter_id")
    op.execute("DROP INDEX IF EXISTS ix_graph_runs_run_id")
    op.execute("DROP TABLE IF EXISTS graph_runs")
