"""drop chapters.body — the prose lives on scenes

The scene step (``666563abba5d``) wrapped every chapter's prose into one scene
and deliberately kept ``chapters.body`` so the models and the history stayed
equal while the last readers moved onto scenes. That move is now complete: the
continuation — the column's final reader — assembles its context from the active
scene's tail and the book's earlier scenes (W4 design §5), so the chapter is a
grouping shell with no prose of its own. This revision retires the column the
wrap copied from; the prose itself already stands on the scenes, untouched.

The model attribute (``Chapter.body``) is removed in the same commit, so the
models-vs-history gate stays equal: neither schema path declares the column.

Revision ID: 58fcdeca1503
Revises: 666563abba5d
Create Date: 2026-11-16 19:10:45.312702

"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "58fcdeca1503"
down_revision: str | Sequence[str] | None = "666563abba5d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The wrap already carried every chapter's prose into its scene; dropping
    # the shell's column loses nothing the scenes do not hold.
    op.drop_column("chapters", "body")


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    re-adding the column would not restore the prose the wrap moved onto the
    scenes. Restore the dump ``prepare_database`` took before the upgrade
    instead (the scene step's convention, one revision up).
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
