"""add documents.byte_size

The upload's own size, stated where the upload is listed: the documents
panel shows it (WP6 §9), computed nowhere new — ingest already counts the
bytes to refuse the 1 MB ceiling, and this keeps that count beside the row
it belonged to all along.

Nullable, no default: there is no live data to backfill, and a document
ingested before this column is honestly unmeasured, not zero bytes.

Revision ID: 6ec29fc5fc0f
Revises: cefe1b1450a1
Create Date: 2026-11-05 10:52:12.312365

"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "6ec29fc5fc0f"
down_revision: str | Sequence[str] | None = "cefe1b1450a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("byte_size", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    restore the dump ``prepare_database`` took before the upgrade instead.
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
