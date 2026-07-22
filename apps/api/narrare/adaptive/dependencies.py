"""DI factories for the adaptive domain (RULE-04 split).

Production wiring for ``AdaptiveContextService`` lives here. The service
is request-scoped (it depends on an ``AsyncSession`` for persistence).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 — needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.adaptive.adaptive_context_provider import AdaptiveContextProviderImpl
    from narrare.adaptive.repository import AdaptiveSettingsRepository
    from narrare.adaptive.service import AdaptiveContextService


def get_adaptive_settings_repository(
    session: SessionDep,
) -> AdaptiveSettingsRepository:
    """Create an AdaptiveSettingsRepository bound to the request session."""
    from narrare.adaptive.repository import AdaptiveSettingsRepository

    return AdaptiveSettingsRepository(session)


def get_adaptive_context_provider(
    session: SessionDep,
) -> AdaptiveContextProviderImpl:
    """Create the production AdaptiveContextProviderImpl.

    Wires PreferenceProvider (mem0-backed, ADR-033) + ProfileProvider
    (None until a Backend ProfileProvider exists — Phase 2 boundary
    preserved) + AdaptiveSettingsRepository (Phase 3 Task 4 — DB-backed).
    """
    from narrare._app.dependencies import (
        _get_preference_service_instance,  # pyright: ignore[reportPrivateUsage]
    )
    from narrare.adaptive.adaptive_context_provider import (
        AdaptiveContextProviderImpl,
    )

    preference_service = _get_preference_service_instance()
    settings_repo = get_adaptive_settings_repository(session)
    return AdaptiveContextProviderImpl(
        preference_provider=preference_service,
        profile_provider=None,
        settings_repo=settings_repo,
    )


def get_adaptive_context_service(
    session: SessionDep,
) -> AdaptiveContextService:
    """Create an AdaptiveContextService with production DI."""
    from narrare.adaptive.service import AdaptiveContextService

    provider = get_adaptive_context_provider(session)
    settings_repo = get_adaptive_settings_repository(session)
    return AdaptiveContextService(provider=provider, settings_repo=settings_repo)
