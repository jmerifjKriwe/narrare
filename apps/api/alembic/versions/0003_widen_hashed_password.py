"""Widen hashed_password from VARCHAR(72) to VARCHAR(255)

Argon2id hashes are ~97 chars and exceed the original bcrypt-oriented
VARCHAR(72) limit.

Revision ID: 0003_widen_hashed_password
Revises: 0002_chapter_versions
Create Date: 2026-05-13 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0003_widen_hashed_password"
down_revision: str | None = "0002_chapter_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(72),
        type_=sa.String(255),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(255),
        type_=sa.String(72),
        nullable=False,
    )
