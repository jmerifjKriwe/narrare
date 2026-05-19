"""Template info service — cascade, diff, and update detection.

Separated from the main CRUD service to keep file sizes under limits.
Handles the more analytical template operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.templates.schemas import DiffResponse, UpdateInfoResponse
from narrare_core.templates import load_default_template

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.templates.repository import TemplateRepository

logger = structlog.get_logger(__name__)


class TemplateInfoService:
    """API service for template info/diff/update operations.

    Requires a repository for DB-backed override lookups.
    """

    def __init__(self, repository: TemplateRepository, session: AsyncSession) -> None:
        self._repo = repository
        self._session = session

    async def cascade_info(
        self,
        entity_type: str,
        language: str,
        *,
        user_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
    ) -> list[dict[str, object]]:
        """Get cascade resolution paths for a template.

        Args:
            entity_type: Entity type (e.g. "character").
            language: Language code (e.g. "en").
            user_id: User UUID, or None.
            project_id: Project UUID, or None.

        Returns:
            List of dicts with level, scope, exists keys.
        """
        paths: list[dict[str, object]] = []

        if user_id:
            user_override = await self._repo.get_override(entity_type, language, "user", user_id)
            paths.append(
                {
                    "level": "user",
                    "scope": "user",
                    "scope_id": str(user_id),
                    "exists": user_override is not None,
                }
            )

        if project_id:
            proj_override = await self._repo.get_override(
                entity_type, language, "project", project_id
            )
            paths.append(
                {
                    "level": "project",
                    "scope": "project",
                    "scope_id": str(project_id),
                    "exists": proj_override is not None,
                }
            )

        raw = load_default_template(entity_type, language)
        paths.append(
            {
                "level": "bundled",
                "scope": "global",
                "scope_id": None,
                "exists": raw is not None,
            }
        )

        return paths

    async def detect_updates(
        self,
        *,
        scope: str = "user",
        scope_id: uuid.UUID | None = None,
    ) -> list[UpdateInfoResponse]:
        """Detect templates where bundled version has changed since override.

        Args:
            scope: Scope level ("user", "project", "global").
            scope_id: Scope identifier, or None for global.

        Returns:
            List of UpdateInfoResponse for templates with available updates.
        """
        from narrare.templates.detection_repository import TemplateDetectionRepository

        detection_repo = TemplateDetectionRepository(self._session)
        updates = await detection_repo.detect_updates(scope, scope_id)
        return [
            UpdateInfoResponse(
                entity_type=u["entity_type"],
                language=u["language"],
                override_version=u["override_version"],
                current_bundled_version=u["current_bundled_version"],
            )
            for u in updates
        ]

    async def get_diff(
        self,
        entity_type: str,
        language: str,
        *,
        scope: str = "user",
        scope_id: uuid.UUID | None = None,
    ) -> DiffResponse | None:
        """Get side-by-side content for an overridden template.

        Args:
            entity_type: Entity type (e.g. "character").
            language: Language code (e.g. "en").
            scope: Scope level ("user", "project", "global").
            scope_id: Scope identifier, or None for global.

        Returns:
            DiffResponse with override and bundled content, or None.
        """
        override = await self._repo.get_override(entity_type, language, scope, scope_id)
        if override is None:
            return None

        raw = load_default_template(entity_type, language)
        bundled_content = raw if raw is not None else ""

        return DiffResponse(
            entity_type=entity_type,
            language=language,
            override_content=override.raw,
            bundled_content=bundled_content,
        )
