"""Prompt management API service — thin wrapper around core PromptManagementService.

Converts core dataclasses to Pydantic response schemas.
No business logic — all logic lives in the core layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.prompts.schemas import (
    CascadePathResponse,
    DiffResponse,
    PromptDetailResponse,
    PromptInfoResponse,
    UpdateInfoResponse,
)

if TYPE_CHECKING:
    from narrare.prompts.schemas import SaveOverrideRequest
    from narrare_core.prompts.management import PromptManagementService

logger = structlog.get_logger(__name__)


class PromptManagementApiService:
    """API service wrapping core PromptManagementService.

    Converts core dataclasses to Pydantic schemas for HTTP responses.
    All prompt management logic is delegated to the core service.
    """

    def __init__(self, core_service: PromptManagementService) -> None:
        self._core = core_service

    async def list_prompts(
        self,
        *,
        category: str | None = None,
    ) -> list[PromptInfoResponse]:
        """List all prompts with optional category filter.

        Args:
            category: Optional category to filter by.

        Returns:
            List of PromptInfoResponse schemas.
        """
        infos = await self._core.list_prompts(category=category)
        return [
            PromptInfoResponse(
                prompt_id=info.prompt_id,
                name=info.name,
                category=info.category,
                language=info.language,
                source=info.source,
                has_override=info.has_override,
                prompt_version=info.prompt_version,
            )
            for info in infos
        ]

    async def get_prompt(self, prompt_id: str) -> PromptDetailResponse | None:
        """Get full prompt detail by ID.

        Args:
            prompt_id: Prompt identifier in {category}/{language}/{mode} format.

        Returns:
            PromptDetailResponse or None if not found.
        """
        detail = await self._core.get_prompt(prompt_id)
        if detail is None:
            return None
        return PromptDetailResponse(
            prompt_id=detail.prompt_id,
            content=detail.content,
            base_content=detail.base_content,
            source=detail.source,
            is_overridden=detail.is_overridden,
            variables=detail.variables,
            metadata=detail.metadata,
        )

    async def save_override(
        self,
        prompt_id: str,
        request: SaveOverrideRequest,
    ) -> None:
        """Save a prompt override.

        Args:
            prompt_id: Prompt identifier.
            request: SaveOverrideRequest with new content.
        """
        await self._core.save_override(prompt_id, request.content)
        logger.info("prompt_override_saved_api", prompt_id=prompt_id)

    async def reset_override(self, prompt_id: str) -> bool:
        """Reset a prompt override, restoring the bundled default.

        Args:
            prompt_id: Prompt identifier.

        Returns:
            True if an override was deleted, False if none existed.
        """
        return await self._core.reset_override(prompt_id)

    async def cascade_info(self, prompt_id: str) -> list[CascadePathResponse]:
        """Get cascade resolution paths for a prompt.

        Args:
            prompt_id: Prompt identifier.

        Returns:
            List of CascadePathResponse with level, path, and existence status.
        """
        paths = await self._core.cascade_info(prompt_id)
        return [
            CascadePathResponse(
                level=p.level,
                path=str(p.path),
                exists=p.exists,
            )
            for p in paths
        ]

    async def detect_updates(self) -> list[UpdateInfoResponse]:
        """Detect prompts where bundled version has changed since override.

        Returns:
            List of UpdateInfoResponse for prompts with available updates.
        """
        updates = await self._core.detect_updates()
        return [
            UpdateInfoResponse(
                prompt_id=u.prompt_id,
                override_version=u.override_version,
                current_bundled_version=u.current_bundled_version,
            )
            for u in updates
        ]

    async def get_diff(self, prompt_id: str) -> DiffResponse | None:
        """Get side-by-side diff content for an overridden prompt.

        Args:
            prompt_id: Prompt identifier.

        Returns:
            DiffResponse with override and bundled content, or None.
        """
        diff = await self._core.get_diff(prompt_id)
        if diff is None:
            return None
        override_content, bundled_content = diff
        return DiffResponse(
            prompt_id=prompt_id,
            override_content=override_content,
            bundled_content=bundled_content,
        )
