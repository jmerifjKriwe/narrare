"""Template routes — thin, delegates immediately to template service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.templates.schemas import (
    DiffResponse,
    SaveOverrideRequest,
    TemplateDetailResponse,
    TemplateInfoResponse,
    UpdateInfoResponse,
)
from narrare.templates.service import str_to_uuid

if TYPE_CHECKING:
    from narrare.templates.info_service import TemplateInfoService
    from narrare.templates.service import TemplateApiService

router = APIRouter(prefix="/novels/{novel_id}/kb/templates", tags=["templates"])


def _service(session: SessionDep) -> TemplateApiService:
    from narrare.templates.repository import TemplateRepository
    from narrare.templates.service import TemplateApiService

    return TemplateApiService(repository=TemplateRepository(session))


def _info_service(session: SessionDep) -> TemplateInfoService:
    from narrare.templates.info_service import TemplateInfoService
    from narrare.templates.repository import TemplateRepository

    return TemplateInfoService(repository=TemplateRepository(session), session=session)


# --- Specific routes before parameterised ones ---


@router.get("/updates", response_model=list[UpdateInfoResponse])
async def detect_updates(
    novel_id: str,
    user_id: CurrentUserIdDep,
    service: TemplateInfoService = Depends(_info_service),
) -> list[UpdateInfoResponse]:
    return await service.detect_updates(scope="user", scope_id=str_to_uuid(user_id))


@router.get("", response_model=list[TemplateInfoResponse])
async def list_templates(
    novel_id: str,
    user_id: CurrentUserIdDep,
    entity_type: str | None = Query(default=None),
    language: str | None = Query(default=None),
    service: TemplateApiService = Depends(_service),
) -> list[TemplateInfoResponse]:
    return await service.list_templates(
        entity_type=entity_type,
        language=language,
        scope="user",
        scope_id=str_to_uuid(user_id),
    )


@router.get("/{entity_type}", response_model=TemplateDetailResponse)
async def get_template(
    novel_id: str,
    entity_type: str,
    user_id: CurrentUserIdDep,
    language: str = Query(default="en"),
    service: TemplateApiService = Depends(_service),
) -> TemplateDetailResponse:
    result = await service.get_template(
        entity_type=entity_type,
        language=language,
        scope="user",
        scope_id=str_to_uuid(user_id),
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="templates.template_not_found"
        )
    return result


@router.get("/{entity_type}/diff", response_model=DiffResponse)
async def get_diff(
    novel_id: str,
    entity_type: str,
    user_id: CurrentUserIdDep,
    language: str = Query(default="en"),
    service: TemplateInfoService = Depends(_info_service),
) -> DiffResponse:
    result = await service.get_diff(
        entity_type=entity_type,
        language=language,
        scope="user",
        scope_id=str_to_uuid(user_id),
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="templates.no_override_for_diff"
        )
    return result


@router.post(
    "/{entity_type}", response_model=TemplateDetailResponse, status_code=status.HTTP_201_CREATED
)
async def save_override(
    novel_id: str,
    entity_type: str,
    request: SaveOverrideRequest,
    user_id: CurrentUserIdDep,
    language: str = Query(default="en"),
    service: TemplateApiService = Depends(_service),
) -> TemplateDetailResponse:
    return await service.save_override(
        entity_type=entity_type,
        language=language,
        request=request,
        scope="user",
        scope_id=str_to_uuid(user_id),
    )


@router.delete("/{entity_type}", response_model=bool)
async def reset_override(
    novel_id: str,
    entity_type: str,
    user_id: CurrentUserIdDep,
    language: str = Query(default="en"),
    service: TemplateApiService = Depends(_service),
) -> bool:
    return await service.reset_override(
        entity_type=entity_type,
        language=language,
        scope="user",
        scope_id=str_to_uuid(user_id),
    )
