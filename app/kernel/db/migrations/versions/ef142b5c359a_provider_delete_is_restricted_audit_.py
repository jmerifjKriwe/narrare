"""the provider pointer restricts; the model marks' audit query gets its index

Two shapes the provider-presets wave's final review pinned, one revision:

The model-to-provider foreign key becomes RESTRICT. The settings service's
delete guard still answers first — a delete the guard sees is a named 409
carrying the models still pointed at the provider — and the database is the
atomic backstop behind it: a model pointer the guard cannot see (a row
written between the guard's read and the delete, or by any path the write
gate does not own) now refuses the delete instead of cascading away
silently. No cascade ever drops a task's model behind a 204.

The audit table gains the index the newest-row read asks for:
``(user_id, profile_id, created_at)`` is exactly the model-mark query's
slice — per user, per model, newest first — so the settings page's failure
mark stays a keyed lookup while ``llm_calls`` grows.

Revision ID: ef142b5c359a
Revises: eee301009ca3
Create Date: 2026-11-09 14:09:04.870501

"""

from collections.abc import Sequence

import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "ef142b5c359a"
down_revision: str | Sequence[str] | None = "eee301009ca3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The pointer first, its name unchanged — only the delete action moves:
    # the guard answers the named 409 while it can see the pointer, and the
    # RESTRICT catches the one it cannot.
    op.drop_constraint(
        op.f("fk_provider_profiles_provider_id_llm_providers"),
        "provider_profiles",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_provider_profiles_provider_id_llm_providers"),
        "provider_profiles",
        "llm_providers",
        ["provider_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    # The model marks' read: user, model, newest first.
    op.create_index(
        "ix_llm_calls_user_id_profile_id_created_at",
        "llm_calls",
        ["user_id", "profile_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    restore the dump ``prepare_database`` took before the upgrade instead.
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
