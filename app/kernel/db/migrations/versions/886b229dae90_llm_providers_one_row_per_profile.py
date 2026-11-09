"""llm providers, one row per profile

The provider table arrives one step ahead of its readers (plan, Task 1): a
user's saved endpoint — vendor, base URL, models URL, the key — which
profiles then point at through ``provider_id`` instead of repeating it.

The backfill is 1:1 with nothing to guess: every existing profile becomes one
provider row carrying the profile's own id, name, kind, endpoint and key, and
the profile's ``provider_id`` is set to that id — its own id, so the stored
key material (Fernet ciphertext in the column, plaintext in the OS keychain
keyed by that same id) stays findable from either side. ``provider_id`` stays
nullable here: the revision that makes it NOT NULL comes once every writer
creates the provider row first, and nothing reads the column yet.

Revision ID: 886b229dae90
Revises: 1da751030eab
Create Date: 2026-11-07 22:31:14.372561

"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "886b229dae90"
down_revision: str | Sequence[str] | None = "1da751030eab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("models_url", sa.String(length=500), nullable=True),
        sa.Column("vendor", sa.String(length=40), nullable=True),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("api_key_hint", sa.String(length=8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_llm_providers_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_providers")),
    )
    op.create_index(op.f("ix_llm_providers_user_id"), "llm_providers", ["user_id"], unique=False)
    op.add_column("provider_profiles", sa.Column("provider_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_provider_profiles_provider_id_llm_providers"),
        "provider_profiles",
        "llm_providers",
        ["provider_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # The backfill runs against whatever profiles exist: one provider row per
    # profile, the profile's own id reused as the provider's id (the 1:1
    # mapping that keeps every keychain secret valid), then the pointer set.
    op.execute("""
        INSERT INTO llm_providers (id, user_id, name, kind, base_url, models_url,
            vendor, api_key, api_key_hint, created_at, updated_at)
        SELECT p.id, p.user_id, p.name, p.kind, p.base_url, NULL, NULL,
            p.api_key, p.api_key_hint, now(), now()
        FROM provider_profiles p
    """)
    op.execute("UPDATE provider_profiles SET provider_id = id")


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    restore the dump ``prepare_database`` took before the upgrade instead.
    Drafts ship the same way: no downgrade body, only this raise.
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
