"""chapter positions are deferrable

The constraint #522 landed — one number per chapter per novel — is plain,
and plain uniqueness checks at statement time: it would refuse the renumber
WP6 adds (a reorder's rewrite, a delete's close-up) because those pass
through intermediate states the finished set does not hold. Rebuilt in its
deferrable form — ``DEFERRABLE INITIALLY DEFERRED`` — the check moves to
commit, where the renumber's set is consistent again. Not amnesty: a real
duplicate still dies, at the commit instead of the statement.

Autogenerate cannot see a deferrability change, so this revision is
hand-written: drop the plain constraint, create the same one deferred.
Same name, same columns — only the check's timing moved.

Revision ID: 10cb78d699b7
Revises: 6ec29fc5fc0f
Create Date: 2026-11-05 10:52:41.996576

"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "10cb78d699b7"
down_revision: str | Sequence[str] | None = "6ec29fc5fc0f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("uq_chapters_novel_id_position"), "chapters", type_="unique")
    op.create_unique_constraint(
        op.f("uq_chapters_novel_id_position"),
        "chapters",
        ["novel_id", "position"],
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    restore the dump ``prepare_database`` took before the upgrade instead.
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
