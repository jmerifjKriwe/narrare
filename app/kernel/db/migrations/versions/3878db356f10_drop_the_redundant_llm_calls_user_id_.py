"""the redundant llm_calls user_id index is dropped

The marks' composite index (``ef142b5c359a``) opens with ``user_id``, so the
baseline's single-column ``ix_llm_calls_user_id`` answers no read the
composite does not already serve — every query it could key is per user, per
model, newest first — while costing its own write on every ``llm_calls`` row
(issue #749). The models carry the same change in the same commit
(``LlmCall`` overrides the inherited ``index=True``), so the
models-vs-history gate stays equal: neither schema path declares the index.

Revision ID: 3878db356f10
Revises: 58fcdeca1503
Create Date: 2026-11-22 14:58:35.591367

"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "3878db356f10"
down_revision: str | Sequence[str] | None = "58fcdeca1503"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The composite carries the reads; the single column's index only ever
    # doubled the write. The marks' index is pinned by name in the gate suite.
    op.drop_index("ix_llm_calls_user_id", table_name="llm_calls")


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    restore the dump ``prepare_database`` took before the upgrade instead.
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
