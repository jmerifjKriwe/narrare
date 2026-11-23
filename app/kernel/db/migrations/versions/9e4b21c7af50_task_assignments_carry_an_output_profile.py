"""task_assignments carry an output profile

The output-profile build (W8, spec §"The three backend builds" item 2): the
assignment grows the task's output choice beside the model it points at.
``output_profile`` names a vocabulary entry or ``custom``; it is NOT NULL
with ``balanced`` as its default — absent and carried null both mean it, so
no two-state semantics live on the column, and the added default backfills
every existing assignment to ``balanced`` in the same step. A custom choice
stores its explicit token number in ``output_profile_custom``; the save gate
bounds that number to the assigned model's stored ``max_output_tokens`` when
one exists. The models carry the same change in the same commit
(``TaskAssignment``), so the models-vs-history gate stays equal.

Revision ID: 9e4b21c7af50
Revises: 3878db356f10
Create Date: 2026-11-23 10:12:44.310921

"""

from collections.abc import Sequence

import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "9e4b21c7af50"
down_revision: str | Sequence[str] | None = "3878db356f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The server_default is the backfill: Postgres fills the existing rows
    # with 'balanced' as the column lands, and stays as the column's default
    # because the model declares the same one.
    op.add_column(
        "task_assignments",
        sa.Column(
            "output_profile", sa.String(length=20), nullable=False, server_default="balanced"
        ),
    )
    op.add_column(
        "task_assignments",
        sa.Column("output_profile_custom", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    restore the dump ``prepare_database`` took before the upgrade instead.
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
