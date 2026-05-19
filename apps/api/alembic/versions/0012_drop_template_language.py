"""Drop language column from kb_templates.

Consolidates multi-language rows (keeps highest based_on_version per group),
drops the old unique constraint that included ``language``, removes the
``language`` column, and adds a new unique constraint on
``(entity_type, scope, scope_id)``.

Idempotent where possible (uses IF EXISTS / IF NOT EXISTS patterns).

Revision ID: 0012_drop_template_language
Revises: 0011_add_concept_setting_types
Create Date: 2026-05-19 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0012_drop_template_language"
down_revision: str | None = "0011_add_concept_setting_types"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop language column and consolidate rows."""
    # Step 1: For each (entity_type, scope, scope_id) group with multiple
    # rows (different languages), keep the one with the highest
    # based_on_version and delete the rest.  Rows with NULL
    # based_on_version are treated as '0.0.0'.
    op.execute(
        """
        DELETE FROM kb_templates
        WHERE id IN (
            SELECT id FROM (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY entity_type, scope, scope_id
                        ORDER BY COALESCE(based_on_version, '0.0.0') DESC,
                                 created_at DESC
                    ) AS rn
                FROM kb_templates
            ) sub
            WHERE rn > 1
        )
        """
    )

    # Step 2: Drop the old unique constraint (includes language)
    op.execute("ALTER TABLE kb_templates DROP CONSTRAINT IF EXISTS uq_kb_templates_unique")

    # Step 3: Drop the language column
    op.execute("ALTER TABLE kb_templates DROP COLUMN IF EXISTS language")

    # Step 4: Add new unique constraint on (entity_type, scope, scope_id)
    op.execute(
        "ALTER TABLE kb_templates ADD CONSTRAINT uq_kb_templates_unique "
        "UNIQUE (entity_type, scope, scope_id)"
    )


def downgrade() -> None:
    """Re-add language column and restore old constraint."""
    # Drop the new unique constraint
    op.execute("ALTER TABLE kb_templates DROP CONSTRAINT IF EXISTS uq_kb_templates_unique")

    # Re-add the language column with default 'en'
    op.execute("ALTER TABLE kb_templates ADD COLUMN language VARCHAR(10) NOT NULL DEFAULT 'en'")

    # Re-add the old unique constraint (now includes language)
    op.execute(
        "ALTER TABLE kb_templates ADD CONSTRAINT uq_kb_templates_unique "
        "UNIQUE (entity_type, language, scope, scope_id)"
    )
