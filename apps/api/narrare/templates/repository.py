"""SQLAlchemy repository for template overrides.

Implements ``TemplateRepositoryProtocol`` against the ``kb_templates`` table.
All DB queries are isolated here — never in services or routers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import structlog
from sqlalchemy import delete, select

from narrare._app.base_repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult
from narrare.templates.models import KBTemplate, TemplateScope
from narrare_core.templates import parse_template

if TYPE_CHECKING:
    import uuid

    from narrare_core.templates import Template

# Note: TemplateDetectionRepository in detection_repository.py
# provides the detect_updates method to keep this file under limit.

logger = structlog.get_logger(__name__)

# Valid entity types — must match the DB check constraint
_VALID_ENTITY_TYPES = frozenset(
    {
        "character",
        "concept",
        "faction",
        "location",
        "object",
        "setting",
        "system",
        "timeline",
    },
)


class TemplateRepository(BaseRepository):
    """Repository for template overrides in the kb_templates table.

    Provides CRUD operations for template overrides at any scope level
    (user, project, global).  Uses upsert semantics for save operations.
    """

    async def get_override(
        self,
        entity_type: str,
        language: str,
        scope: str,
        scope_id: uuid.UUID | None,
    ) -> Template | None:
        """Look up a single template override.

        Args:
            entity_type: Entity type (e.g. "character").
            language: Language code (e.g. "en", "de", "fr").
            scope: Scope level ("user", "project", "global").
            scope_id: Scope identifier, or None for global.

        Returns:
            Parsed Template if found, or None.
        """
        stmt = select(KBTemplate).where(
            KBTemplate.entity_type == entity_type,
            KBTemplate.language == language,
            KBTemplate.scope == TemplateScope(scope),
            KBTemplate.scope_id == scope_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return parse_template(row.content)

    async def list_overrides(
        self,
        scope: str,
        scope_id: uuid.UUID | None,
    ) -> list[Template]:
        """List all template overrides for a given scope.

        Args:
            scope: Scope level ("user", "project", "global").
            scope_id: Scope identifier, or None for global.

        Returns:
            List of parsed Templates.
        """
        stmt = select(KBTemplate).where(
            KBTemplate.scope == TemplateScope(scope),
            KBTemplate.scope_id == scope_id,
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [parse_template(row.content) for row in rows]

    async def save_override(
        self,
        entity_type: str,
        language: str,
        scope: str,
        scope_id: uuid.UUID | None,
        content: str,
        *,
        based_on_version: str | None = None,
    ) -> Template:
        """Insert or update a template override (upsert).

        Uses the unique constraint to perform an upsert: tries to find
        an existing row first, then inserts or updates accordingly.

        Args:
            entity_type: Entity type (e.g. "character").
            language: Language code (e.g. "en", "de", "fr").
            scope: Scope level ("user", "project", "global").
            scope_id: Scope identifier, or None for global.
            content: Full template content (YAML frontmatter + body markdown).
            based_on_version: The bundled template version this is based on.

        Returns:
            The parsed, persisted Template.
        """
        # Check for existing row
        stmt = select(KBTemplate).where(
            KBTemplate.entity_type == entity_type,
            KBTemplate.language == language,
            KBTemplate.scope == TemplateScope(scope),
            KBTemplate.scope_id == scope_id,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.content = content
            existing.based_on_version = based_on_version
            existing.schema_version = "2.0.0"
            db_row = existing
        else:
            db_row = KBTemplate(
                entity_type=entity_type,
                language=language,
                scope=TemplateScope(scope),
                scope_id=scope_id,
                content=content,
                based_on_version=based_on_version,
                schema_version="2.0.0",
            )
            self._session.add(db_row)

        await self._flush_and_refresh(db_row)
        logger.info(
            "template_override_saved",
            entity_type=entity_type,
            language=language,
            scope=scope,
            scope_id=str(scope_id) if scope_id else None,
        )
        return parse_template(db_row.content)

    async def delete_override(
        self,
        entity_type: str,
        language: str,
        scope: str,
        scope_id: uuid.UUID | None,
    ) -> bool:
        """Delete a template override.

        Args:
            entity_type: Entity type (e.g. "character").
            language: Language code (e.g. "en", "de", "fr").
            scope: Scope level ("user", "project", "global").
            scope_id: Scope identifier, or None for global.

        Returns:
            True if a row was deleted, False otherwise.
        """
        stmt = delete(KBTemplate).where(
            KBTemplate.entity_type == entity_type,
            KBTemplate.language == language,
            KBTemplate.scope == TemplateScope(scope),
            KBTemplate.scope_id == scope_id,
        )
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        deleted = result.rowcount > 0
        if deleted:
            logger.info(
                "template_override_deleted",
                entity_type=entity_type,
                language=language,
                scope=scope,
                scope_id=str(scope_id) if scope_id else None,
            )
        return deleted
