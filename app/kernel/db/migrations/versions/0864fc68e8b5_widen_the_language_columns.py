"""widen the language columns

Revision ID: 0864fc68e8b5
Revises: 12fc7ddcec6f
Create Date: 2026-11-26 19:26:22.899774

"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "0864fc68e8b5"
down_revision: str | Sequence[str] | None = "12fc7ddcec6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "users", "locale", existing_type=sa.String(8), type_=sa.String(64), existing_nullable=True
    )
    op.alter_column(
        "novels",
        "language",
        existing_type=sa.String(16),
        type_=sa.String(64),
        existing_nullable=True,
    )


def downgrade() -> None:
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
