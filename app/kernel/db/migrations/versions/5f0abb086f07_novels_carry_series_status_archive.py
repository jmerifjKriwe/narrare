"""novels carry series status archive

The shelf rebuild (W3) tracks three answers the library surface reads:
where a book stands (``status``), which series it belongs to and as
which volume (``series_id``, ``series_volume``), and whether it left the
main grid (``archived_at``). The series themselves are user-owned rows
in their own table — the shelf groups by them, and a later wave edits
them.

Every column is nullable and carries no default: a novel that predates
the fields or has not answered keeps ``NULL``, the honest answer, not a
value it does not have. The status vocabulary (``draft``, ``revision``,
``final``) is checked at the writing service boundary, not by the
column; the series link is SET NULL, so a series going away ungroups its
books instead of taking them with it; ``archived_at`` is a timestamp,
not a flag, so the archive view can say when.

Revision ID: 5f0abb086f07
Revises: b8387f85a796
Create Date: 2026-11-15 09:25:07.061859

"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "5f0abb086f07"
down_revision: str | Sequence[str] | None = "b8387f85a796"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "series",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_series_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_series")),
    )
    op.create_index(op.f("ix_series_user_id"), "series", ["user_id"], unique=False)
    op.add_column("novels", sa.Column("status", sa.String(length=20), nullable=True))
    op.add_column("novels", sa.Column("series_id", sa.Uuid(), nullable=True))
    op.add_column("novels", sa.Column("series_volume", sa.Integer(), nullable=True))
    op.add_column("novels", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_novels_series_id_series"),
        "novels",
        "series",
        ["series_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    restore the dump ``prepare_database`` took before the upgrade instead.
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
