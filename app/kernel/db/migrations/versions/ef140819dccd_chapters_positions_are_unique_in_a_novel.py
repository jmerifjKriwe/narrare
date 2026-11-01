"""chapters positions are unique in a novel

A novel's chapters are ordered by ``position`` — one number per chapter,
the table's invariant (#521). The models have declared the unique
constraint since that race fix; this revision carries it to the databases
an already-running app holds, which is the only thing a revision is for.

Pure schema, no data rewrite: a database that already holds two chapters
at one position fails this constraint creation with Postgres's own named
error, and repairing such rows is a judgment call this history does not
make for its operator.

Revision ID: ef140819dccd
Revises: b47f335cacca
Create Date: 2026-11-01 13:17:59.461352

"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "ef140819dccd"
down_revision: str | Sequence[str] | None = "b47f335cacca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        op.f("uq_chapters_novel_id_position"), "chapters", ["novel_id", "position"]
    )


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    restore the dump ``prepare_database`` took before the upgrade instead.
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
