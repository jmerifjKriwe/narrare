"""HTTP surface for the settings. Parses, delegates, returns; no logic here.

The profile routes translate the service's closed error vocabulary into the
HTTP one: a missing profile is 404, the gate's refusals are 422s naming their
fields, the default guard and a create or default swap that lost the race are
409s, a key store that cannot take or produce a key is a 503, and a discovery that
cannot reach its endpoint is a 502. A failed connection *test* is none of
these — it is the 200 that carries the failure, because the test ran.
"""

from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.settings.profiles_service import (
    DefaultProfileError,
    DefaultProfileRaceError,
    NoEndpointError,
    ProfileNotFoundError,
    ProfileRefusedError,
    ProfileService,
)
from app.capabilities.settings.schemas import (
    AssignmentRead,
    AssignmentUpdate,
    ProfileCreate,
    ProfileCreated,
    ProfileRead,
    ProfileTestResult,
    ProfileUpdate,
    SettingsRead,
    SettingsUpdate,
    TaskEffectiveRead,
)
from app.capabilities.settings.service import SettingsService
from app.kernel.auth import SetupRequiredError, current_user_id
from app.kernel.db.session import get_session
from app.kernel.llm.models import ProviderProfile
from app.kernel.secrets import KeyUnavailableError, NoKeyStoreError

router = APIRouter(prefix="/api/settings", tags=["settings"])

logger = getLogger("narrare")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]


def _service(session: SessionDep, user_id: UserDep) -> SettingsService:
    return SettingsService(session, user_id)


ServiceDep = Annotated[SettingsService, Depends(_service)]


def _profiles(session: SessionDep, user_id: UserDep) -> ProfileService:
    return ProfileService(session, user_id)


ProfileServiceDep = Annotated[ProfileService, Depends(_profiles)]


def _masked(profile: ProviderProfile) -> ProfileRead:
    """The row as every read shows it: the mask, never the key."""
    return ProfileRead(
        id=profile.id,
        name=profile.name,
        kind=profile.kind,
        base_url=profile.base_url,
        model=profile.model,
        api_key_mask=f"sk-…{profile.api_key_hint}" if profile.api_key_hint else None,
        is_default=profile.is_default,
        context_window=profile.context_window,
        max_output_tokens=profile.max_output_tokens,
        temperature=profile.temperature,
        request_timeout=profile.request_timeout,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _refusal(error: ProfileRefusedError) -> HTTPException:
    """The gate's refusal as a 422 naming each missing or refused field."""
    return HTTPException(
        status_code=422,
        detail=[
            {"loc": ["body", field], "msg": str(error), "type": "value_error"}
            for field in error.fields
        ],
    )


def _profile_errors(error: Exception) -> HTTPException:
    """The service vocabulary's mapping, shared by every profile route."""
    if isinstance(error, ProfileNotFoundError):
        return HTTPException(status_code=404, detail="profile not found")
    if isinstance(error, ProfileRefusedError):
        return _refusal(error)
    if isinstance(error, DefaultProfileError | NoEndpointError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, DefaultProfileRaceError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, NoKeyStoreError):
        return HTTPException(status_code=503, detail=str(error))
    return HTTPException(status_code=500, detail=str(error))


@router.get("", response_model=SettingsRead)
async def get_settings(service: ServiceDep) -> SettingsRead:
    return SettingsRead(locale=await service.read_locale())


@router.patch("", response_model=SettingsRead)
async def update_settings(payload: SettingsUpdate, service: ServiceDep) -> SettingsRead:
    try:
        locale = await service.write_locale(payload.locale)
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    return SettingsRead(locale=locale)


@router.get("/profiles", response_model=list[ProfileRead])
async def list_profiles(service: ProfileServiceDep) -> list[ProfileRead]:
    """The user's profiles, the default first; every key read shows the mask."""
    return [_masked(profile) for profile in await service.list()]


@router.post("/profiles", response_model=ProfileCreated, status_code=201)
async def create_profile(payload: ProfileCreate, service: ProfileServiceDep) -> ProfileCreated:
    """Store one profile; the first becomes the default; the full key returns once."""
    try:
        profile, api_key = await service.create(payload)
    except ProfileRefusedError as error:
        raise _refusal(error) from None
    except DefaultProfileRaceError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except NoKeyStoreError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    return ProfileCreated(**_masked(profile).model_dump(), api_key=api_key)


@router.patch("/profiles/{profile_id}", response_model=ProfileRead)
async def update_profile(
    profile_id: UUID, payload: ProfileUpdate, service: ProfileServiceDep
) -> ProfileRead:
    """Apply the patch; an empty ``api_key`` keeps the stored one."""
    try:
        profile = await service.update(profile_id, payload)
    except (
        ProfileNotFoundError,
        ProfileRefusedError,
        DefaultProfileRaceError,
        NoKeyStoreError,
    ) as error:
        raise _profile_errors(error) from None
    return _masked(profile)


@router.delete("/profiles/{profile_id}", status_code=204)
async def delete_profile(profile_id: UUID, service: ProfileServiceDep) -> None:
    """Delete a non-default profile; its assignments cascade with it."""
    try:
        await service.delete(profile_id)
    except (ProfileNotFoundError, DefaultProfileError, NoKeyStoreError) as error:
        raise _profile_errors(error) from None


@router.post("/profiles/{profile_id}/test", response_model=ProfileTestResult)
async def test_profile(profile_id: UUID, service: ProfileServiceDep) -> ProfileTestResult:
    """One cheap completion against the profile's endpoint, audited as settings.test."""
    try:
        result = await service.test(profile_id)
    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="profile not found") from None
    return ProfileTestResult(ok=result.ok, error=result.error, latency_ms=result.latency_ms)


@router.get("/profiles/{profile_id}/models", response_model=list[str])
async def list_profile_models(profile_id: UUID, service: ProfileServiceDep) -> list[str]:
    """Model discovery against the profile's endpoint."""
    try:
        return await service.discover(profile_id)
    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="profile not found") from None
    except NoEndpointError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except KeyUnavailableError as error:
        raise HTTPException(status_code=502, detail=str(error)) from None
    except Exception:
        logger.exception("model discovery failed for profile %s", profile_id)
        raise HTTPException(status_code=502, detail="model discovery failed") from None


@router.get("/assignments", response_model=list[AssignmentRead])
async def list_assignments(service: ProfileServiceDep) -> list[AssignmentRead]:
    """Every task assignment of the user's, ordered by task key."""
    return [
        AssignmentRead(task_key=assignment.task_key, profile_id=assignment.profile_id)
        for assignment in await service.assignments()
    ]


@router.put("/assignments/{task_key}", response_model=AssignmentRead)
async def put_assignment(
    task_key: Annotated[str, Path(min_length=1)],
    payload: AssignmentUpdate,
    service: ProfileServiceDep,
) -> AssignmentRead:
    """Point the task at a profile, or clear it with ``profile_id: null``.

    Any non-empty task key is accepted — unknown keys are forward-compatible.
    """
    try:
        assignment = await service.assign(task_key, payload.profile_id)
    except (ProfileNotFoundError, ProfileRefusedError) as error:
        raise _profile_errors(error) from None
    return AssignmentRead(
        task_key=task_key, profile_id=assignment.profile_id if assignment else None
    )


@router.get("/tasks", response_model=list[TaskEffectiveRead])
async def list_tasks(service: ProfileServiceDep) -> list[TaskEffectiveRead]:
    """The effective provider per known task key, for the page's task list.

    Reads only: each row is the resolution cascade's answer, never a write
    and never an audit row. A profile whose key its tier can no longer
    produce fails the read by name — 502, as discovery maps the same class —
    so a lost key is never a bare 500.
    """
    try:
        rows = await service.tasks()
    except KeyUnavailableError as error:
        raise HTTPException(status_code=502, detail=str(error)) from None
    return [
        TaskEffectiveRead(
            task_key=row.task_key,
            profile_id=row.profile_id,
            profile_name=row.profile_name,
            kind=row.kind,
            assignable=row.assignable,
        )
        for row in rows
    ]
