"""Project AI settings service — project-level overrides with source metadata.

Manages project-level model and token limit overrides. Project overrides
cascade over user-level settings — when a project has an override, it
takes precedence regardless of the user's configuration.

Returns effective settings with source information so the UI can show
where each setting comes from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import uuid

    from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
    from narrare.settings.schemas import (
        ProjectAiSettingsResponse,
        UpdateProjectAiSettingsRequest,
    )
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository

logger = structlog.get_logger(__name__)


class ProjectAiSettingsService:
    """Service for managing project-level AI overrides.

    Args:
        project_ai_repo: Repository for project AI settings.
        user_ai_repo: Repository for user AI settings (for effective resolution).
    """

    def __init__(
        self,
        project_ai_repo: ProjectAiSettingsRepository,
        user_ai_repo: UserAiSettingsRepository,
        token_limits_service: TokenLimitsService | None = None,
    ) -> None:
        self._project_ai_repo = project_ai_repo
        self._user_ai_repo = user_ai_repo
        self._token_limits_service = token_limits_service

    async def get_settings(
        self,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> ProjectAiSettingsResponse:
        """Get project AI settings.

        Args:
            user_id: The user's UUID (for authorization).
            novel_id: The novel's UUID.

        Returns:
            Project AI settings response.
        """
        settings = await self._project_ai_repo.get(novel_id)

        from narrare.settings.schemas import ProjectAiSettingsResponse

        return ProjectAiSettingsResponse(
            novel_id=settings.novel_id,
            category_overrides=settings.category_overrides or {},
            intent_overrides=settings.intent_overrides or {},
            token_limit_overrides=settings.token_limit_overrides or {},
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
            user_id: The user's UUID (for authorization).
            novel_id: The novel's UUID.
            request: Update data with optional fields.

        Returns:
            Updated project AI settings response.
        """
        updates = request.model_dump(exclude_none=True)

        # Dual-write to TokenLimitsService (DEPRECATED — old columns)
        if self._token_limits_service and "token_limit_overrides" in updates:
            logger.warning(
                "token_limit_overrides_write_deprecated",
                user_id=str(user_id),
                project_id=str(novel_id),
            )
            await self._token_limits_service.update_project_limits(
                project_id=str(novel_id),
                overrides={"legacy_per_category_overrides": updates["token_limit_overrides"]},
            )

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
            token_limit_overrides=settings.token_limit_overrides or {},
            updated_at=settings.updated_at,
        )
