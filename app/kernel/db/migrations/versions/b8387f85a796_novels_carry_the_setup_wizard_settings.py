"""novels carry the setup wizard settings

The welcome/setup rebuild (W2) collects five per-novel answers the first
run did not ask for: a word goal, the author's typology, the dramatic form,
the AI's role and the canon strictness. They land on the novel's row — the
spec leaves columns vs. a settings table to the plan, and five nullable
columns are the smaller shape.

Every column is nullable and carries no default: a novel whose wizard was
skipped or predates the fields keeps ``NULL``, the honest answer, not a
value it does not have. The setup schema validates the vocabularies
(``author_typology``, ``ai_role``) and the ranges (``target_words`` >= 1,
``canon_strictness`` 1-5); ``dramatic_form`` stays a free string until the
template wave pins its vocabulary. A demo import keeps the archive's own
title/genre and still binds these settings onto the imported novel.

Revision ID: b8387f85a796
Revises: 386a3dbd7e04
Create Date: 2026-11-14 09:20:43.478267

"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "b8387f85a796"
down_revision: str | Sequence[str] | None = "386a3dbd7e04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("novels", sa.Column("target_words", sa.Integer(), nullable=True))
    op.add_column("novels", sa.Column("author_typology", sa.String(length=40), nullable=True))
    op.add_column("novels", sa.Column("dramatic_form", sa.String(length=80), nullable=True))
    op.add_column("novels", sa.Column("ai_role", sa.String(length=40), nullable=True))
    op.add_column("novels", sa.Column("canon_strictness", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    restore the dump ``prepare_database`` took before the upgrade instead.
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
