"""HTTP surface for the settings. Parses, delegates, returns; no logic here.

The model routes translate the service's closed error vocabulary into the
HTTP one: a missing model is 404, the gate's refusals are 422s naming their
fields (a ``provider_id`` that is not the user's among them), the default
guard and a create or default swap that lost the race are 409s, and a failed
connection *test* is none of these — it is the 200 that carries the failure,
because the test ran. The models keep the ``/api/settings/profiles`` paths
until the rename revision; only their payloads speak of models.

The provider routes speak the same dialect: a missing provider is 404, the
gate's refusals are 422s naming their fields, a delete a model still points
at is a 409 naming the models, a key store that cannot take or produce a key
is a 503, and a discovery that cannot reach its endpoint is a 502.
"""

from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.settings.profiles_service import (
    DefaultProfileError,
    DefaultProfileRaceError,
    ModelService,
    NoEndpointError,
    ProfileNotFoundError,
    ProfileRefusedError,
)
from app.capabilities.settings.providers_service import (
    ProviderHasModelsError,
    ProviderNotFoundError,
    ProviderRefusedError,
    ProviderService,
)
from app.capabilities.settings.schemas import (
    AssignmentRead,
    AssignmentUpdate,
    ModelCreate,
    ModelRead,
    ModelTestResult,
    ModelUpdate,
    ProviderCreate,
    ProviderCreated,
    ProviderRead,
    ProviderUpdate,
    SettingsRead,
    SettingsThemeRead,
    SettingsThemeUpdate,
    SettingsUpdate,
    TaskEffectiveRead,
)
from app.capabilities.settings.service import SettingsService
from app.kernel.auth import SetupRequiredError, current_user_id
from app.kernel.db.session import get_session
from app.kernel.llm.models import LLMProvider, ProviderProfile
from app.kernel.secrets import KeyUnavailableError, NoKeyStoreError

router = APIRouter(prefix="/api/settings", tags=["settings"])

logger = getLogger("narrare")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]


def _service(session: SessionDep, user_id: UserDep) -> SettingsService:
    return SettingsService(session, user_id)


ServiceDep = Annotated[SettingsService, Depends(_service)]


def _models(session: SessionDep, user_id: UserDep) -> ModelService:
    return ModelService(session, user_id)


ModelServiceDep = Annotated[ModelService, Depends(_models)]


def _providers(session: SessionDep, user_id: UserDep) -> ProviderService:
    return ProviderService(session, user_id)


ProviderServiceDep = Annotated[ProviderService, Depends(_providers)]


def _masked(profile: ProviderProfile, provider_name: str) -> ModelRead:
    """The model as every read shows it: its provider named, no key anywhere."""
    return ModelRead(
        id=profile.id,
        name=profile.name,
        provider_id=profile.provider_id,  # pyright: ignore[reportArgumentType]  the gate keeps it set
        provider_name=provider_name,
        model=profile.model or "",
        is_default=profile.is_default,
        context_window=profile.context_window,
        max_output_tokens=profile.max_output_tokens,
        temperature=profile.temperature,
        request_timeout=profile.request_timeout,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _provider_masked(provider: LLMProvider) -> ProviderRead:
    """The provider row as every read shows it: the mask, never the key."""
    return ProviderRead(
        id=provider.id,
        name=provider.name,
        kind=provider.kind,
        base_url=provider.base_url,
        models_url=provider.models_url,
        vendor=provider.vendor,
        api_key_mask=f"sk-…{provider.api_key_hint}" if provider.api_key_hint else None,
    )


def _refusal(error: ProfileRefusedError | ProviderRefusedError) -> HTTPException:
    """The gate's refusal as a 422 naming each missing or refused field."""
    return HTTPException(
        status_code=422,
        detail=[
            {"loc": ["body", field], "msg": str(error), "type": "value_error"}
            for field in error.fields
        ],
    )


def _profile_errors(error: Exception) -> HTTPException:
    """The service vocabulary's mapping, shared by every model route."""
    if isinstance(error, ProfileNotFoundError):
        return HTTPException(status_code=404, detail="profile not found")
    if isinstance(error, ProfileRefusedError):
        return _refusal(error)
    if isinstance(error, DefaultProfileError | DefaultProfileRaceError):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=500, detail=str(error))


def _provider_errors(error: Exception) -> HTTPException:
    """The provider service vocabulary's mapping, shared by every provider route."""
    if isinstance(error, ProviderNotFoundError):
        return HTTPException(status_code=404, detail="provider not found")
    if isinstance(error, ProviderRefusedError):
        return _refusal(error)
    if isinstance(error, ProviderHasModelsError | NoEndpointError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, NoKeyStoreError):
        return HTTPException(status_code=503, detail=str(error))
    return HTTPException(status_code=500, detail=str(error))


@router.get("", response_model=SettingsRead)
async def get_settings(service: ServiceDep) -> SettingsRead:
    return SettingsRead(locale=await service.read_locale(), theme=await service.read_theme())


@router.patch("", response_model=SettingsRead)
async def update_settings(payload: SettingsUpdate, service: ServiceDep) -> SettingsRead:
    try:
        locale = await service.write_locale(payload.locale)
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    return SettingsRead(locale=locale, theme=await service.read_theme())


@router.patch("/theme", response_model=SettingsThemeRead)
async def update_theme(payload: SettingsThemeUpdate, service: ServiceDep) -> SettingsThemeRead:
    try:
        theme = await service.write_theme(payload.theme)
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    return SettingsThemeRead(theme=theme)


@router.get("/profiles", response_model=list[ModelRead])
async def list_profiles(service: ModelServiceDep) -> list[ModelRead]:
    """The user's models, the default first; every read names its provider."""
    return [_masked(profile, provider.name) for profile, provider in await service.list()]


@router.post("/profiles", response_model=ModelRead, status_code=201)
async def create_profile(payload: ModelCreate, service: ModelServiceDep) -> ModelRead:
    """Store one model under one of the user's providers; the first is the default."""
    try:
        profile, provider = await service.create(payload)
    except (ProfileRefusedError, DefaultProfileRaceError) as error:
        raise _profile_errors(error) from None
    return _masked(profile, provider.name)


@router.patch("/profiles/{profile_id}", response_model=ModelRead)
async def update_profile(
    profile_id: UUID, payload: ModelUpdate, service: ModelServiceDep
) -> ModelRead:
    """Apply the patch; the provider and the model string can both move."""
    try:
        profile, provider = await service.update(profile_id, payload)
    except (ProfileNotFoundError, ProfileRefusedError, DefaultProfileRaceError) as error:
        raise _profile_errors(error) from None
    return _masked(profile, provider.name)


@router.delete("/profiles/{profile_id}", status_code=204)
async def delete_profile(profile_id: UUID, service: ModelServiceDep) -> None:
    """Delete a non-default model; its assignments cascade with it."""
    try:
        await service.delete(profile_id)
    except (ProfileNotFoundError, DefaultProfileError) as error:
        raise _profile_errors(error) from None


@router.post("/profiles/{profile_id}/test", response_model=ModelTestResult)
async def test_profile(profile_id: UUID, service: ModelServiceDep) -> ModelTestResult:
    """One cheap completion through the model's provider, audited as settings.test."""
    try:
        result = await service.test(profile_id)
    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="profile not found") from None
    return ModelTestResult(ok=result.ok, error=result.error, latency_ms=result.latency_ms)


@router.get("/providers", response_model=list[ProviderRead])
async def list_providers(service: ProviderServiceDep) -> list[ProviderRead]:
    """The user's providers, by name; every key read shows the mask."""
    return [_provider_masked(provider) for provider in await service.list()]


@router.post("/providers", response_model=ProviderCreated, status_code=201)
async def create_provider(payload: ProviderCreate, service: ProviderServiceDep) -> ProviderCreated:
    """Store one provider endpoint; the full key returns once."""
    try:
        provider, api_key = await service.create(payload)
    except ProviderRefusedError as error:
        raise _refusal(error) from None
    except NoKeyStoreError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    return ProviderCreated(**_provider_masked(provider).model_dump(), api_key=api_key)


@router.patch("/providers/{provider_id}", response_model=ProviderRead)
async def update_provider(
    provider_id: UUID, payload: ProviderUpdate, service: ProviderServiceDep
) -> ProviderRead:
    """Apply the patch; an empty ``api_key`` keeps the stored one."""
    try:
        provider = await service.update(provider_id, payload)
    except (ProviderNotFoundError, ProviderRefusedError, NoKeyStoreError) as error:
        raise _provider_errors(error) from None
    return _provider_masked(provider)


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(provider_id: UUID, service: ProviderServiceDep) -> None:
    """Delete a provider no model points at; the guard names the models otherwise."""
    try:
        await service.delete(provider_id)
    except (ProviderNotFoundError, ProviderHasModelsError, NoKeyStoreError) as error:
        raise _provider_errors(error) from None


@router.get("/providers/{provider_id}/models", response_model=list[str])
async def list_provider_models(provider_id: UUID, service: ProviderServiceDep) -> list[str]:
    """Model discovery against the provider's endpoint."""
    try:
        return await service.discover(provider_id)
    except ProviderNotFoundError:
        raise HTTPException(status_code=404, detail="provider not found") from None
    except NoEndpointError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except KeyUnavailableError as error:
        raise HTTPException(status_code=502, detail=str(error)) from None
    except Exception:
        logger.exception("model discovery failed for provider %s", provider_id)
        raise HTTPException(status_code=502, detail="model discovery failed") from None


@router.get("/assignments", response_model=list[AssignmentRead])
async def list_assignments(service: ModelServiceDep) -> list[AssignmentRead]:
    """Every task assignment of the user's, ordered by task key."""
    return [
        AssignmentRead(task_key=assignment.task_key, profile_id=assignment.profile_id)
        for assignment in await service.assignments()
    ]


@router.put("/assignments/{task_key}", response_model=AssignmentRead)
async def put_assignment(
    task_key: Annotated[str, Path(min_length=1)],
    payload: AssignmentUpdate,
    service: ModelServiceDep,
) -> AssignmentRead:
    """Point the task at a model, or clear it with ``profile_id: null``.

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
async def list_tasks(service: ModelServiceDep) -> list[TaskEffectiveRead]:
    """The effective provider per known task key, for the page's task list.

    Reads only: each row is the resolution cascade's answer, never a write
    and never an audit row. A provider whose key its tier can no longer
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
