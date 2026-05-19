"""Add 'concept' and 'setting' to entity_type CHECK constraints.

Expands the CHECK constraints on both ``kb_entries`` and ``kb_templates``
to accept the two new entity types: ``concept`` and ``setting``.

PostgreSQL requires dropping and recreating CHECK constraints since they
cannot be altered in-place.

Revision ID: 0011_add_concept_setting_types
Revises: 0010_kb_templates
Create Date: 2026-05-19 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0011_add_concept_setting_types"
down_revision: str | None = "0010_kb_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All valid entity types (new canonical set)
_VALID_TYPES = (
    "'character', 'concept', 'faction', 'location', 'object', 'setting', 'system', 'timeline'"
)


def upgrade() -> None:
    """Expand CHECK constraints to include concept and setting."""
    # kb_entries
    op.execute("ALTER TABLE kb_entries DROP CONSTRAINT IF EXISTS ck_kb_entries_entity_type")
    op.execute(
        f"ALTER TABLE kb_entries ADD CONSTRAINT ck_kb_entries_entity_type "
        f"CHECK (entity_type IN ({_VALID_TYPES}))"
    )

    # kb_templates
    op.execute("ALTER TABLE kb_templates DROP CONSTRAINT IF EXISTS ck_kb_templates_entity_type")
    op.execute(
        f"ALTER TABLE kb_templates ADD CONSTRAINT ck_kb_templates_entity_type "
        f"CHECK (entity_type IN ({_VALID_TYPES}))"
    )


def downgrade() -> None:
    """Revert CHECK constraints to the original 6 types."""
    _old_types = "'character', 'location', 'faction', 'object', 'system', 'timeline'"

    # kb_entries
    op.execute("ALTER TABLE kb_entries DROP CONSTRAINT IF EXISTS ck_kb_entries_entity_type")
    op.execute(
        f"ALTER TABLE kb_entries ADD CONSTRAINT ck_kb_entries_entity_type "
        f"CHECK (entity_type IN ({_old_types}))"
    )

    # kb_templates
    op.execute("ALTER TABLE kb_templates DROP CONSTRAINT IF EXISTS ck_kb_templates_entity_type")
    op.execute(
        f"ALTER TABLE kb_templates ADD CONSTRAINT ck_kb_templates_entity_type "
        f"CHECK (entity_type IN ({_old_types}))"
    )
