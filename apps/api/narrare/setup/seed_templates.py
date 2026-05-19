"""Seed bundled default templates into the database.

Iterates all bundled default templates and upserts them as 'global' scope
entries in the ``kb_templates`` table.  New entries are inserted; existing
global entries are updated when the bundled version is newer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from packaging.version import Version

from narrare.templates.models import KBTemplate, TemplateScope
from narrare_core.templates import list_default_templates, load_default_template, parse_template

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def seed_templates(session: AsyncSession) -> int:
    """Seed all bundled default templates into the kb_templates table.

    For each entity type from bundled defaults, inserts a new 'global'
    scope entry if none exists.  When an existing global entry is found,
    updates it only if the bundled version is newer than the stored version.
    User-scope and project-scope entries are never touched.

    Args:
        session: SQLAlchemy async session.

    Returns:
        Number of templates inserted or updated.
    """
    from sqlalchemy import select

    bundled = list_default_templates()
    upserted = 0

    for entity_type in bundled:
        # Load bundled template content first (needed for both insert & update)
        raw = load_default_template(entity_type)
        if raw is None:
            logger.warning(
                "template_seed_skipped_missing",
                entity_type=entity_type,
            )
            continue

        template = parse_template(raw)
        based_on_version = template.meta.template_version

        # Check if global entry already exists
        stmt = select(KBTemplate).where(
            KBTemplate.entity_type == entity_type,
            KBTemplate.scope == TemplateScope.GLOBAL,
            KBTemplate.scope_id.is_(None),
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            # Insert new global entry
            session.add(
                KBTemplate(
                    entity_type=entity_type,
                    scope=TemplateScope.GLOBAL,
                    scope_id=None,
                    content=raw,
                    based_on_version=based_on_version,
                    schema_version=template.meta.schema_version,
                )
            )
            upserted += 1
            logger.info(
                "template_seeded",
                entity_type=entity_type,
                version=based_on_version,
            )
            continue

        # Existing global entry — update if bundled version is newer
        existing_version = existing.based_on_version or "0.0.0"
        if Version(based_on_version) > Version(existing_version):
            existing.content = raw
            existing.based_on_version = based_on_version
            existing.schema_version = template.meta.schema_version
            upserted += 1
            logger.info(
                "template_seed_updated",
                entity_type=entity_type,
                old_version=existing_version,
                new_version=based_on_version,
            )
            continue

        logger.debug(
            "template_seed_skipped_exists",
            entity_type=entity_type,
            version=existing_version,
        )

    return upserted
