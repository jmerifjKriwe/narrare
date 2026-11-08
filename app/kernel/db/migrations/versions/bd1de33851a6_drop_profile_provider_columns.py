"""drop the provider columns the model no longer owns

Schema step B of the provider cut (plan, Task 4): the endpoint facts a
model row still carried — ``kind``, ``base_url``, ``api_key``,
``api_key_hint`` — are gone, and the pointer to the row that owns them is
no longer optional.

``provider_id`` goes NOT NULL first: the previous revision's backfill gave
every existing profile its 1:1 provider row, and the writers since Task 3
create the provider before the model, so no NULL can remain. The four
duplicated columns then drop with their facts — the provider row has held
the truth since the backfill copied it, and nothing has read the copies
since. A model row is now a name, a provider pointer, a model string and
the tuning.

Revision ID: bd1de33851a6
Revises: 886b229dae90
Create Date: 2026-11-08 10:10:29.559098

"""

from collections.abc import Sequence

import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "bd1de33851a6"
down_revision: str | Sequence[str] | None = "886b229dae90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The pointer first: the backfill left no NULL behind, so the constraint
    # holds the moment it lands — and the drops below can no longer produce
    # a row without its provider.
    op.alter_column("provider_profiles", "provider_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("provider_profiles", "kind")
    op.drop_column("provider_profiles", "base_url")
    op.drop_column("provider_profiles", "api_key")
    op.drop_column("provider_profiles", "api_key_hint")


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    restore the dump ``prepare_database`` took before the upgrade instead.
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
