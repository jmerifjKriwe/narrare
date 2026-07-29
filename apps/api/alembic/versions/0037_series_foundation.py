"""Series Foundation: series + series_settings tables, novels & kb_entries scope columns.

Spec 1 (Series Foundation) Slice 1, Task 1.5 — the Alembic migration that
materialises ALL schema changes from Tasks 1.2-1.4 in one atomic file
(RULE-14: a migration lands in the SAME task batch as its model changes;
no ``Base.metadata.create_all()`` in integration tests).

What this migration does, in order:

1. Create ``series`` (the reihe grouping novels) + ``ck_series_status`` CHECK
   + ``ix_series_user_id``.
2. Create ``series_settings`` (1:1, ``series_id`` UNIQUE FK ON DELETE CASCADE).
   ``author_voice`` is present but empty/nullable in Spec 1 (Spec 3 fills it).
3. ALTER ``novels``: add ``series_id`` (nullable FK, ON DELETE SET NULL → the
   novel becomes standalone if its series is deleted), ``series_position``,
   ``subtitle``; + ``ix_novels_series_id`` + ``uq_novels_series_position``.
4. ALTER ``kb_entries``: add ``series_id`` (FK ON DELETE CASCADE),
   ``base_entry_id`` (self-FK ON DELETE SET NULL); make ``novel_id`` NULLABLE
   (NULL = Series-Canon entry); + indexes on both new columns.
5. DROP the old ``uq_kb_entries_novel_slug`` unique constraint (it assumed
   every entry belongs to a novel — false once Canon entries exist).
6. CREATE two PARTIAL unique indexes replacing it:
   - ``uq_kb_canon_per_series`` (series_id, slug) WHERE novel_id IS NULL
   - ``uq_kb_overlay_per_novel`` (novel_id, slug) WHERE novel_id IS NOT NULL
7. CREATE ``ck_kb_entries_scope_invariant`` CHECK enforcing the scope rule:
   a Canon entry (novel_id IS NULL) MUST set series_id and MUST NOT set
   base_entry_id; an Overlay entry simply requires novel_id.

Design notes
------------
The DB-level CHECK constraints and partial unique indexes are intentionally
expressed ONLY here, not in the ORM models — mirroring the established
slice pattern (Task 1.4 already documented this in ``kb/models.py``).
Autogenerate is a starting point, not a parity gate: ``alembic check`` is
not run in CI; the migration correctness gate is ``alembic upgrade head``
(CI + ``tests/integration/conftest.py``). ``series.status`` carries a
``server_default='draft'`` (DB-level safety for non-ORM inserts) even though
the ORM model declares only a Python-side ``default='draft'``.

Backward compatibility: existing ``WHERE novel_id = X`` queries still work —
Canon entries have ``novel_id IS NULL`` and are simply absent from
novel-scoped queries.

See:
    Spec 1 design doc — Series Foundation + KB Evolution.
    ADR-075 — Novel series membership.
    Task 1.4 (``kb/models.py``) — the partial-index/CHECK pattern mirrored here.

Revision ID: 0037_series_foundation
Revises: 0036_author_voice_column
Create Date: 2026-07-29 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0037_series_foundation"
down_revision: str | None = "0036_author_voice_column"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. series table ──────────────────────────────────────────────────
    op.create_table(
        "series",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("subtitle", sa.String(500), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("genre", sa.String(100), nullable=True),
        sa.Column("writing_language", sa.String(100), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("planned_novel_count", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'completed')",
            name="ck_series_status",
        ),
    )
    op.create_index("ix_series_user_id", "series", ["user_id"])

    # ── 2. series_settings table (1:1, author_voice empty in Spec 1) ─────
    op.create_table(
        "series_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "series_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("series.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("author_voice", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── 3. novels: series membership columns ─────────────────────────────
    op.add_column(
        "novels",
        sa.Column(
            "series_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("series.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "novels",
        sa.Column("series_position", sa.Integer, nullable=True),
    )
    op.add_column(
        "novels",
        sa.Column("subtitle", sa.String(500), nullable=True),
    )
    op.create_index("ix_novels_series_id", "novels", ["series_id"])
    op.create_unique_constraint(
        "uq_novels_series_position",
        "novels",
        ["series_id", "series_position"],
    )

    # ── 4. kb_entries: scope discriminator columns ───────────────────────
    op.add_column(
        "kb_entries",
        sa.Column(
            "series_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("series.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "kb_entries",
        sa.Column(
            "base_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kb_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    # novel_id becomes nullable: NULL = Series-Canon entry (Schema 2A).
    op.alter_column("kb_entries", "novel_id", nullable=True)
    op.create_index("ix_kb_entries_series_id", "kb_entries", ["series_id"])
    op.create_index("ix_kb_entries_base_entry_id", "kb_entries", ["base_entry_id"])

    # ── 5. Drop old unique constraint (assumed every entry has a novel) ──
    op.drop_constraint("uq_kb_entries_novel_slug", "kb_entries", type_="unique")

    # ── 6. Partial unique indexes (Canon per series + Overlay per novel) ─
    op.create_index(
        "uq_kb_canon_per_series",
        "kb_entries",
        ["series_id", "slug"],
        unique=True,
        postgresql_where=sa.text("novel_id IS NULL"),
    )
    op.create_index(
        "uq_kb_overlay_per_novel",
        "kb_entries",
        ["novel_id", "slug"],
        unique=True,
        postgresql_where=sa.text("novel_id IS NOT NULL"),
    )

    # ── 7. Scope-invariant CHECK ─────────────────────────────────────────
    # Canon (novel_id IS NULL) MUST set series_id and MUST NOT set base_entry_id.
    op.create_check_constraint(
        "ck_kb_entries_scope_invariant",
        "kb_entries",
        "(novel_id IS NULL AND series_id IS NOT NULL AND base_entry_id IS NULL) "
        "OR (novel_id IS NOT NULL)",
    )


def downgrade() -> None:
    # Reverse order of upgrade(). Each step mirrors its upgrade counterpart.
    # ── 7. Drop scope-invariant CHECK ────────────────────────────────────
    op.drop_constraint("ck_kb_entries_scope_invariant", "kb_entries", type_="check")

    # ── 6. Drop partial unique indexes ───────────────────────────────────
    op.drop_index("uq_kb_overlay_per_novel", table_name="kb_entries")
    op.drop_index("uq_kb_canon_per_series", table_name="kb_entries")

    # ── 5. Recreate old unique constraint ────────────────────────────────
    # Safe only after all Canon entries (novel_id IS NULL) are gone — the
    # caller is responsible for removing them before running this downgrade.
    op.create_unique_constraint(
        "uq_kb_entries_novel_slug",
        "kb_entries",
        ["novel_id", "slug"],
    )

    # ── 4. Drop kb_entries scope columns; restore novel_id NOT NULL ──────
    op.drop_index("ix_kb_entries_base_entry_id", table_name="kb_entries")
    op.drop_index("ix_kb_entries_series_id", table_name="kb_entries")
    # Restoring NOT NULL fails if any NULL novel_id rows remain; see step 5.
    op.alter_column("kb_entries", "novel_id", nullable=False)
    op.drop_column("kb_entries", "base_entry_id")
    op.drop_column("kb_entries", "series_id")

    # ── 3. Drop novels series columns ────────────────────────────────────
    op.drop_constraint("uq_novels_series_position", "novels", type_="unique")
    op.drop_index("ix_novels_series_id", table_name="novels")
    op.drop_column("novels", "subtitle")
    op.drop_column("novels", "series_position")
    op.drop_column("novels", "series_id")

    # ── 2. Drop series_settings table ────────────────────────────────────
    op.drop_table("series_settings")

    # ── 1. Drop series table + index ─────────────────────────────────────
    op.drop_index("ix_series_user_id", table_name="series")
    op.drop_table("series")
