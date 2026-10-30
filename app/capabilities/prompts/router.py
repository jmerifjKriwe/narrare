"""HTTP surface for the prompts. Parses, delegates, returns; no logic here.

The save-time gate's refusals are 422s that name their reason — the render's
own (``syntax``, ``undefined-variable``, ``include-cycle``, …) beside the
scope rules' (``novel-scope``, ``unknown-novel``, ``contract``) — and an
unknown key is a 404 on every route. The save answers with the fresh detail;
the reset is the house's no-content 204, idempotent for a scope with no row.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.prompts.schemas import (
    PromptDetail,
    PromptDiff,
    PromptKeyNotFound,
    PromptRefusal,
    PromptSave,
    PromptSummary,
    ValidationBody,
)
from app.capabilities.prompts.service import (
    PromptNotFoundError,
    PromptRefusedError,
    PromptService,
)
from app.kernel.auth import current_user_id
from app.kernel.db.session import get_session

router = APIRouter(prefix="/api/prompts", tags=["prompts"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]


def _service(session: SessionDep, user_id: UserDep) -> PromptService:
    return PromptService(session, user_id)


ServiceDep = Annotated[PromptService, Depends(_service)]

# The declared failure contracts, shared by every route that can hit them.
# The 422 model is a union: the gate's refusal body beside the framework's
# own request-validation body — a declared model replaces the canned
# validation schema, so the union keeps both honest for the typed client.
# The list route takes no key, so it documents no 404. The annotation is
# the framework's own parameter type — ``Any`` carries its model-or-schema
# slot, nothing else.
_REFUSED_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {
        "description": "Refused by name — or the request failed validation.",
        "model": PromptRefusal | ValidationBody,
    },
}
_NOT_FOUND_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"description": "No bundled prompt carries this key.", "model": PromptKeyNotFound},
}
_KEY_RESPONSES = _NOT_FOUND_RESPONSES | _REFUSED_RESPONSES


def _refused(error: PromptRefusedError) -> HTTPException:
    """The gate's refusal as a 422 naming its reason and its detail."""
    return HTTPException(status_code=422, detail={"reason": error.reason, "detail": str(error)})


def _errors(error: Exception) -> HTTPException:
    """The service vocabulary's mapping, shared by every route."""
    if isinstance(error, PromptNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, PromptRefusedError):
        return _refused(error)
    return HTTPException(status_code=500, detail=str(error))


@router.get("", response_model=list[PromptSummary], responses=_REFUSED_RESPONSES)
async def list_prompts(service: ServiceDep, novel_id: UUID | None = None) -> list[PromptSummary]:
    """Every bundled prompt with its facts and its two override tiers."""
    try:
        return await service.list(novel_id)
    except PromptRefusedError as error:
        raise _refused(error) from None


@router.get("/{key}", response_model=PromptDetail, responses=_KEY_RESPONSES)
async def get_prompt(
    service: ServiceDep,
    key: Annotated[str, Path(min_length=1)],
    novel_id: UUID | None = None,
) -> PromptDetail:
    """One prompt as the editor shows it: bundled source, legend, override."""
    try:
        return await service.detail(key, novel_id)
    except (PromptNotFoundError, PromptRefusedError) as error:
        raise _errors(error) from None


@router.put("/{key}", response_model=PromptDetail, responses=_KEY_RESPONSES)
async def put_prompt(
    service: ServiceDep,
    key: Annotated[str, Path(min_length=1)],
    payload: PromptSave,
) -> PromptDetail:
    """Validate and save the override for the scope; the fresh detail answers."""
    try:
        return await service.save(key, payload.content, payload.novel_id)
    except (PromptNotFoundError, PromptRefusedError) as error:
        raise _errors(error) from None


@router.delete("/{key}", status_code=204, responses=_KEY_RESPONSES)
async def delete_prompt(
    service: ServiceDep,
    key: Annotated[str, Path(min_length=1)],
    novel_id: UUID | None = None,
) -> None:
    """Reset the override for the scope; the other tier is untouched."""
    try:
        await service.delete(key, novel_id)
    except (PromptNotFoundError, PromptRefusedError) as error:
        raise _errors(error) from None


@router.get("/{key}/diff", response_model=PromptDiff, responses=_KEY_RESPONSES)
async def get_prompt_diff(
    service: ServiceDep,
    key: Annotated[str, Path(min_length=1)],
    novel_id: UUID | None = None,
) -> PromptDiff:
    """The bundled template against the override in force for the scope."""
    try:
        return await service.diff(key, novel_id)
    except (PromptNotFoundError, PromptRefusedError) as error:
        raise _errors(error) from None
