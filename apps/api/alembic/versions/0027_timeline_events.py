"""Add timeline_events table for PLAN-004 timeline management.

Creates the persistent timeline event model for narrative temporal
tracking. Supports both manually created events and AI-generated ones,
with references to KB entities (characters, locations) via UUID.

Revision ID: 0027_timeline_events
Revises: 0026_active_generation_unique
Create Date: 2026-06-01 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0027_timeline_events"
down_revision: str | None = "0026_active_generation_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "timeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "novel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("novels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("event_type", sa.String(50), server_default="plot_point", nullable=False),
        # Temporal data
        sa.Column("timestamp_raw", sa.String(200), server_default="", nullable=False),
        sa.Column("timestamp_normalized", sa.String(200), server_default="", nullable=False),
        sa.Column("temporal_order", sa.Integer(), nullable=True),
        # Chapter reference (optional)
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # KB entity references (hybrid model)
        sa.Column(
            "character_refs",
            postgresql.JSONB(),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("location_ref", postgresql.JSONB(), nullable=True),
        # Causal links
        sa.Column("causes", sa.Text(), server_default="", nullable=False),
        sa.Column("consequences", sa.Text(), server_default="", nullable=False),
        # Provenance
        sa.Column("source", sa.String(20), server_default="manual", nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "is_confirmed",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        # Audit
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Indexes
    op.create_index("ix_timeline_events_novel_id", "timeline_events", ["novel_id"])
    op.create_index("ix_timeline_events_chapter_id", "timeline_events", ["chapter_id"])
    op.create_index(
        "ix_timeline_events_novel_order",
        "timeline_events",
        ["novel_id", "temporal_order"],
    )
    op.create_index(
        "ix_timeline_events_novel_type",
        "timeline_events",
        ["novel_id", "event_type"],
    )
    op.create_index(
        "ix_timeline_events_source",
        "timeline_events",
        ["novel_id", "source"],
        postgresql_where=sa.text("source != 'manual'"),
    )

    # Check constraints
    op.create_check_constraint(
        "ck_timeline_events_source",
        "timeline_events",
        sa.text("source IN ('manual', 'ai_analysis', 'extracted')"),
    )
    op.create_check_constraint(
        "ck_timeline_events_event_type",
        "timeline_events",
        sa.text(
            "event_type IN ("
            "'plot_point', 'character_event', 'world_event', "
            "'flashback', 'flashforward', 'birth', 'death', "
            "'battle', 'journey', 'other'"
            ")"
        ),
    )
    op.create_check_constraint(
        "ck_timeline_events_confidence",
        "timeline_events",
        sa.text("confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)"),
    )


def downgrade() -> None:
    op.drop_table("timeline_events")
