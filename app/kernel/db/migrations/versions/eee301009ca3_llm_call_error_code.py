"""llm_calls carries the wire code of a failed call

Schema step of the failure-codes cut (plan, Task 8): a stream that died no
longer ends in an empty frame — it names its cause, and the audit row keeps
the same code beside the error text. The column is nullable on purpose: a
clean call has no code, and neither does a stream the consumer walked away
from — nothing failed there that a code could name.

Revision ID: eee301009ca3
Revises: bd1de33851a6
Create Date: 2026-11-08 18:55:48.967503

"""

from collections.abc import Sequence

import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "eee301009ca3"
down_revision: str | Sequence[str] | None = "bd1de33851a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("llm_calls", sa.Column("error_code", sa.String(length=40), nullable=True))


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    restore the dump ``prepare_database`` took before the upgrade instead.
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
