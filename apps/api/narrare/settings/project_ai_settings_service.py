"""Project AI settings service — project-level overrides.

Manages project-level model and intent overrides. Project overrides
cascade over user-level settings — when a project has an override, it
takes precedence regardless of the user's configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
    from narrare.settings.schemas import (
        ProjectAiSettingsResponse,
        UpdateProjectAiSettingsRequest,
    )
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository

logger = structlog.get_logger(__name__)


class ProjectAiSettingsService:
    """Service for managing project-level AI overrides.

    Args:
        project_ai_repo: Repository for project AI settings.
        user_ai_repo: Repository for user AI settings (for effective resolution).
        novel_repo: Novel repository — the ownership gate (IDOR remediation
            S11b). Project AI overrides steer the victim project's LLM
            calls, so a foreign caller must never read or write them.
    """

    def __init__(
        self,
        project_ai_repo: ProjectAiSettingsRepository,
        user_ai_repo: UserAiSettingsRepository,
        novel_repo: NovelRepositoryProtocol,
    ) -> None:
        self._project_ai_repo = project_ai_repo
        self._user_ai_repo = user_ai_repo
        self._novel_repo = novel_repo

    async def _verify_novel_owned(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Raise ``NotFoundError`` unless ``user_id`` owns ``novel_id``.

        Foreign ≡ unknown (anti-enumeration): both surface as 404. The
        gate MUST run before ``project_ai_repo`` is touched — its ``get``
        auto-creates a settings row on first read.
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

    async def get_settings(
        self,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> ProjectAiSettingsResponse:
        """Get project AI settings.

        Args:
            user_id: The caller's UUID — ownership gate input; a caller
                who does not own ``novel_id`` gets a 404 before any read.
            novel_id: The novel's UUID.

        Returns:
            Project AI settings response.
        """
        await self._verify_novel_owned(novel_id, user_id)
        settings = await self._project_ai_repo.get(novel_id)

        from narrare.settings.schemas import ProjectAiSettingsResponse

        return ProjectAiSettingsResponse(
            novel_id=settings.novel_id,
            category_overrides=settings.category_overrides or {},
            intent_overrides=settings.intent_overrides or {},
            updated_at=settings.updated_at,
        )

    async def update_settings(
        self,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
        request: UpdateProjectAiSettingsRequest,
    ) -> ProjectAiSettingsResponse:
        """Update project AI overrides.

        Args:
            user_id: The caller's UUID — ownership gate input; a caller
                who does not own ``novel_id`` gets a 404 before any write.
            novel_id: The novel's UUID.
            request: Update data with optional fields.

        Returns:
            Updated project AI settings response.
        """
        await self._verify_novel_owned(novel_id, user_id)
        updates = request.model_dump(exclude_none=True)

        if updates:
            settings = await self._project_ai_repo.update(novel_id, **updates)
        else:
            settings = await self._project_ai_repo.get(novel_id)

        logger.info(
            "project_ai_settings_updated",
            user_id=str(user_id),
            novel_id=str(novel_id),
            fields_updated=list(updates.keys()),
        )

        from narrare.settings.schemas import ProjectAiSettingsResponse

        return ProjectAiSettingsResponse(
            novel_id=settings.novel_id,
            category_overrides=settings.category_overrides or {},
            intent_overrides=settings.intent_overrides or {},
            updated_at=settings.updated_at,
        )
