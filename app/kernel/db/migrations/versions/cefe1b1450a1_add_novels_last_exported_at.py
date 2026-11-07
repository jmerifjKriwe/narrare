"""add novels.last_exported_at

The export's trace (WP6 D1): every successful export — path or ZIP —
writes the moment into the novel's row, and nothing else does. The delete
dialogs compare it with the newest change and warn; a refusal would be
theatre, and the comparison is the one statement that is actually true.

The column is nullable and carries no default: a novel never exported
keeps ``NULL``, which is the honest answer, not a timestamp it does not
have.

Revision ID: cefe1b1450a1
Revises: ef140819dccd
Create Date: 2026-11-05 10:51:22.434999

"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "cefe1b1450a1"
down_revision: str | Sequence[str] | None = "ef140819dccd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "novels", sa.Column("last_exported_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    restore the dump ``prepare_database`` took before the upgrade instead.
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
