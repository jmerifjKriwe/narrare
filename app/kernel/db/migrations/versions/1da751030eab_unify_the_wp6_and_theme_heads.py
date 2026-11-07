"""unify the wp6 and theme heads

The WP6 branch and main each grew a migration chain from
``ef140819dccd`` (positions unique): WP6's reorder work continued through
the deferrable constraint while main's visual identity gave the users row
a theme column. A merge that carries both sides carries both chains, and
alembic refuses two heads — this revision is the empty splice that makes
one history of them. Nothing runs here: both sides' tables already agree,
the branches never touched the same table, and the next revision continues
from one head again.

Revision ID: 1da751030eab
Revises: 10cb78d699b7, c4a1e7b2d9f0
Create Date: 2026-11-06 20:15:10.758284

"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "1da751030eab"
down_revision: str | Sequence[str] | None = ("10cb78d699b7", "c4a1e7b2d9f0")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
