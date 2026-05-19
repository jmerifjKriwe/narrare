"""Template override service — manages user template overrides.

For now: stub implementation with protocol methods.  Full CRUD on
overrides is future scope (KB-006).  Records ``based_on_version``
for version tracking.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import uuid

    from narrare_core.templates import Template

logger = structlog.get_logger(__name__)


class TemplateOverrideService:
    """Service for managing user template overrides.

    Currently a stub — returns ``None`` for all lookups.
    Full implementation deferred to KB-006.
    """

    async def get_override(
        self,
        user_id: uuid.UUID,
        entity_type: str,
        language: str,
        *,
        project_id: uuid.UUID | None = None,
    ) -> Template | None:
        """Look up a user/project-level template override.

        Returns ``None`` until override storage is implemented.
        """
        logger.debug(
            "template_override_lookup",
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

        Stub — no-op until override storage is implemented.
        """
        logger.debug(
            "template_override_save_skipped",
            user_id=str(user_id),
            entity_type=entity_type,
            language=language,
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

        Returns ``False`` (nothing deleted) until storage is implemented.
        """
        logger.debug(
            "template_override_delete_skipped",
            user_id=str(user_id),
            entity_type=entity_type,
            language=language,
        )
        return False
