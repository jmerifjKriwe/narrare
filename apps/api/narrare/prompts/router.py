"""Prompts routes — thin, delegates immediately to prompt management service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status

from narrare._app.dependencies import CurrentUserIdDep
from narrare.prompts.schemas import (
    CascadePathResponse,
    DiffResponse,
    PromptDetailResponse,
    PromptInfoResponse,
    SaveOverrideRequest,
    UpdateInfoResponse,
)

if TYPE_CHECKING:
    from narrare.prompts.service import PromptManagementApiService

router = APIRouter(prefix="/prompts", tags=["prompts"])


async def _get_service() -> PromptManagementApiService:
    """Factory for PromptManagementApiService."""
    from narrare._app.dependencies import get_registry
    from narrare.prompts.service import PromptManagementApiService
    from narrare_core.prompts.management import PromptManagementService

    registry = get_registry()  # pyright: ignore[reportPrivateUsage]
    core_service = PromptManagementService(registry=registry)
    return PromptManagementApiService(core_service=core_service)


# --- IMPORTANT: Specific routes must be defined BEFORE /{prompt_id} to avoid path conflicts ---


@router.get("/updates", response_model=list[UpdateInfoResponse])
async def detect_updates(
    user_id: CurrentUserIdDep,
    service: PromptManagementApiService = Depends(_get_service),
) -> list[UpdateInfoResponse]:
    """Detect prompts with available bundled updates."""
    return await service.detect_updates()


@router.get("/{prompt_id:path}/cascade", response_model=list[CascadePathResponse])
async def cascade_info(
    prompt_id: str,
    user_id: CurrentUserIdDep,
    service: PromptManagementApiService = Depends(_get_service),
) -> list[CascadePathResponse]:
    """Get cascade resolution paths for a prompt."""
    return await service.cascade_info(prompt_id)


@router.get("/{prompt_id:path}/diff", response_model=DiffResponse | None)
async def get_diff(
    prompt_id: str,
    user_id: CurrentUserIdDep,
    service: PromptManagementApiService = Depends(_get_service),
) -> DiffResponse | None:
    """Get side-by-side diff for an overridden prompt."""
    result = await service.get_diff(prompt_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="prompts.no_override_for_diff",
        )
    return result


@router.get("", response_model=list[PromptInfoResponse])
async def list_prompts(
    user_id: CurrentUserIdDep,
    category: str | None = Query(default=None),
    service: PromptManagementApiService = Depends(_get_service),
) -> list[PromptInfoResponse]:
    """List all prompts with optional category filter."""
    return await service.list_prompts(category=category)


@router.get("/{prompt_id:path}", response_model=PromptDetailResponse)
async def get_prompt(
    prompt_id: str,
    user_id: CurrentUserIdDep,
    service: PromptManagementApiService = Depends(_get_service),
) -> PromptDetailResponse:
    """Get full prompt detail by ID."""
    result = await service.get_prompt(prompt_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="prompts.not_found")
    return result


@router.put("/{prompt_id:path}", status_code=status.HTTP_204_NO_CONTENT)
async def save_override(
    prompt_id: str,
    request: SaveOverrideRequest,
    user_id: CurrentUserIdDep,
    service: PromptManagementApiService = Depends(_get_service),
) -> None:
    """Save a prompt override."""
    await service.save_override(prompt_id, request)


@router.delete("/{prompt_id:path}/override", response_model=bool)
async def reset_override(
    prompt_id: str,
    user_id: CurrentUserIdDep,
    service: PromptManagementApiService = Depends(_get_service),
) -> bool:
    """Reset a prompt override, restoring bundled default."""
    return await service.reset_override(prompt_id)
