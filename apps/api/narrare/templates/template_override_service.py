"""Template override service — manages user template overrides.

Full CRUD on overrides backed by the template repository.
Records ``based_on_version`` for version tracking and cascade resolution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import uuid

    from narrare.templates.repository import TemplateRepository
    from narrare_core.templates import Template

logger = structlog.get_logger(__name__)


class TemplateOverrideService:
    """Service for managing user template overrides.

    Delegates all storage to ``TemplateRepository``.  Provides the same
    interface as the original stub but with real DB-backed operations.
    """

    def __init__(self, repository: TemplateRepository) -> None:
        """Initialize with a template repository.

        Args:
            repository: Template repository for DB access.
        """
        self._repo = repository

    async def get_override(
        self,
        user_id: uuid.UUID,
        entity_type: str,
        language: str,
        *,
        project_id: uuid.UUID | None = None,
    ) -> Template | None:
        """Look up a user/project-level template override.

        Tries user scope first, then project scope if project_id provided.

        Args:
            user_id: User UUID.
            entity_type: Entity type (e.g. "character").
            language: Language code (e.g. "en", "de", "fr").
            project_id: Optional project UUID for project-scope fallback.

        Returns:
            Parsed Template if found, or None.
        """
        # Try user override first
        user_tpl = await self._repo.get_override(entity_type, language, "user", user_id)
        if user_tpl is not None:
            logger.debug(
                "template_override_found_user",
                user_id=str(user_id),
                entity_type=entity_type,
                language=language,
            )
            return user_tpl

        # Try project override
        if project_id is not None:
            proj_tpl = await self._repo.get_override(
                entity_type,
                language,
                "project",
                project_id,
            )
            if proj_tpl is not None:
                logger.debug(
                    "template_override_found_project",
                    project_id=str(project_id),
                    entity_type=entity_type,
                    language=language,
                )
                return proj_tpl

        logger.debug(
            "template_override_not_found",
            user_id=str(user_id),
            entity_type=entity_type,
            language=language,
            project_id=str(project_id) if project_id else None,
        )
        return None

    async def save_override(
        self,
        user_id: uuid.UUID,
        entity_type: str,
        language: str,
        template: Template,
        based_on_version: str,
        *,
        project_id: uuid.UUID | None = None,
    ) -> None:
        """Save a user/project-level template override.

        Args:
            user_id: User UUID.
            entity_type: Entity type (e.g. "character").
            language: Language code (e.g. "en").
            template: The template to save as override.
            based_on_version: Bundled version this override is based on.
            project_id: If provided, saves as project-scope override.
        """
        scope = "project" if project_id is not None else "user"
        scope_id = project_id if project_id is not None else user_id

        await self._repo.save_override(
            entity_type=entity_type,
            language=language,
            scope=scope,
            scope_id=scope_id,
            content=template.raw,
            based_on_version=based_on_version,
        )

        logger.info(
            "template_override_saved",
            user_id=str(user_id),
            entity_type=entity_type,
            language=language,
            scope=scope,
            based_on_version=based_on_version,
        )

    async def delete_override(
        self,
        user_id: uuid.UUID,
        entity_type: str,
        language: str,
        *,
        project_id: uuid.UUID | None = None,
    ) -> bool:
        """Delete a user/project-level template override.

        Args:
            user_id: User UUID.
            entity_type: Entity type (e.g. "character").
            language: Language code (e.g. "en").
            project_id: If provided, deletes project-scope override.

        Returns:
            True if an override was deleted, False otherwise.
        """
        scope = "project" if project_id is not None else "user"
        scope_id = project_id if project_id is not None else user_id

        deleted = await self._repo.delete_override(
            entity_type=entity_type,
            language=language,
            scope=scope,
            scope_id=scope_id,
        )

        if deleted:
            logger.info(
                "template_override_deleted",
                user_id=str(user_id),
                entity_type=entity_type,
                language=language,
                scope=scope,
            )
        else:
            logger.debug(
                "template_override_delete_skipped",
                user_id=str(user_id),
                entity_type=entity_type,
                language=language,
            )

        return deleted
