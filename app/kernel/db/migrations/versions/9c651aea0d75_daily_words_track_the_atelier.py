"""daily words track the atelier

The shelf rebuild (W3) tracks the atelier's writing: one row per novel
per day, carrying the day's net words. The chapter write path feeds it
with the diff of the shelf's one whitespace rule — the old body read
before the update lands, same-day upserts accumulating against the
composite primary key, deletes counting negative. ``words`` keeps the
honest net, so a day that removed more text than it added is negative,
not floored at zero; the banner's sparkline shows that truth.

The user key is the row's own (rule 4), so the atelier aggregate scopes
without a join through the novel; the novel's foreign key cascades — a
deleted book takes its activity with it, the chapters' own rule. The
words default is the model's own (a fresh row starts at zero before the
first diff lands), not a server default.

Revision ID: 9c651aea0d75
Revises: 5f0abb086f07
Create Date: 2026-11-15 10:11:47.813531

"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "9c651aea0d75"
down_revision: str | Sequence[str] | None = "5f0abb086f07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_words",
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("words", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["novel_id"],
            ["novels.id"],
            name=op.f("fk_daily_words_novel_id_novels"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_daily_words_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("novel_id", "date", name=op.f("pk_daily_words")),
    )
    op.create_index(op.f("ix_daily_words_user_id"), "daily_words", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    restore the dump ``prepare_database`` took before the upgrade instead.
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
