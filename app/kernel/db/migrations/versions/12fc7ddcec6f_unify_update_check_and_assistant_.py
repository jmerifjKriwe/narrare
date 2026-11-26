"""unify update check and assistant sessions

Main and the update-check branch each grew a migration from
``9e4b21c7af50``: the entity interview added ``assistant_sessions`` and
``assistant_turns`` while this branch added the update-check columns to
``users``. A merge that carries both sides carries both chains, and alembic
refuses two heads — this revision is the empty splice that makes one history
of them. Nothing runs here; both sides' changes are already present and the
next revision continues from one head again.

Revision ID: 12fc7ddcec6f
Revises: 32e3fd14068e, d88eb433096c
Create Date: 2026-11-26 12:09:04.787741

"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "12fc7ddcec6f"
down_revision: str | Sequence[str] | None = ("32e3fd14068e", "d88eb433096c")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
