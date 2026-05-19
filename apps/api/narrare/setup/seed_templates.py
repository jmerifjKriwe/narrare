"""Seed bundled default templates into the database.

Iterates all bundled default templates and inserts them as 'global' scope
entries in the ``kb_templates`` table if they don't already exist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.templates.models import KBTemplate, TemplateScope
from narrare_core.templates import list_default_templates, load_default_template, parse_template

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def seed_templates(session: AsyncSession) -> int:
    """Seed all bundled default templates into the kb_templates table.

    For each (entity_type, language) pair from bundled defaults, checks
    whether a 'global' scope entry already exists.  If not, inserts one
    with the full template content and ``based_on_version`` set to the
    template's bundled version.

    Args:
        session: SQLAlchemy async session.

    Returns:
        Number of templates inserted.
    """
    from sqlalchemy import select

    bundled = list_default_templates()
    inserted = 0

    for entity_type, language in bundled:
        # Check if global override already exists
        stmt = select(KBTemplate).where(
            KBTemplate.entity_type == entity_type,
            KBTemplate.language == language,
            KBTemplate.scope == TemplateScope.GLOBAL,
            KBTemplate.scope_id.is_(None),
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            logger.debug(
                "template_seed_skipped_exists",
                entity_type=entity_type,
                language=language,
            )
            continue

        # Load bundled template content
        raw = load_default_template(entity_type, language)
        if raw is None:
            logger.warning(
                "template_seed_skipped_missing",
                entity_type=entity_type,
                language=language,
            )
            continue

        # Extract version from parsed template
        template = parse_template(raw)
        based_on_version = template.meta.template_version

        # Insert global override
        kb_template = KBTemplate(
            entity_type=entity_type,
            language=language,
            scope=TemplateScope.GLOBAL,
            scope_id=None,
            content=raw,
            based_on_version=based_on_version,
            schema_version=template.meta.schema_version,
        )
        session.add(kb_template)
        inserted += 1

        logger.info(
            "template_seeded",
            entity_type=entity_type,
            language=language,
            version=based_on_version,
        )

    return inserted
