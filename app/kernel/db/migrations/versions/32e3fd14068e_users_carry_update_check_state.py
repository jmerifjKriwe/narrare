"""users carry update check state

The update check (design 2026-11-24): the interval is the user's answer and the
last-known release is the answer the API can still give while the release
source is offline. ``update_check_interval_days`` is NOT NULL with seven as its
default — the product default, backfilled into every existing row by the same
step — and the five state columns are nullable: no check has run and no release
has been heard yet, which is exactly what NULL says.

The models carry the same change in the same commit (``app/kernel/contracts/
user.py``), so the models-vs-history gate stays equal.

Revision ID: 32e3fd14068e
Revises: 9e4b21c7af50
Create Date: 2026-11-24 15:52:17.265542

"""

from collections.abc import Sequence

import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "32e3fd14068e"
down_revision: str | Sequence[str] | None = "9e4b21c7af50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("update_check_interval_days", sa.Integer(), server_default="7", nullable=False),
    )
    op.add_column(
        "users", sa.Column("last_update_check_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users", sa.Column("dismissed_update_version", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "users", sa.Column("last_known_latest_version", sa.String(length=64), nullable=True)
    )
    op.add_column("users", sa.Column("last_known_release_notes", sa.Text(), nullable=True))
    op.add_column(
        "users", sa.Column("last_known_release_url", sa.String(length=2048), nullable=True)
    )


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    restore the dump ``prepare_database`` took before the upgrade instead.
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
