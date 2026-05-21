"""Add rating column to feedback_events table.

Adds an optional 1-5 integer rating to feedback_events so users can
score AI suggestions alongside the existing accept/reject/modify action.

Revision ID: 0017_feedback_rating
Revises: 0016_custom_tones
Create Date: 2026-05-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0017_feedback_rating"
down_revision = "0016_custom_tones"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add rating column with CHECK constraint (1-5)."""
    op.add_column(
        "feedback_events",
        sa.Column("rating", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_feedback_events_rating_range",
        "feedback_events",
        "rating IS NULL OR (rating >= 1 AND rating <= 5)",
    )


def downgrade() -> None:
    """Remove rating column and its CHECK constraint."""
    op.drop_constraint(
        "ck_feedback_events_rating_range",
        "feedback_events",
        type_="check",
    )
    op.drop_column("feedback_events", "rating")
