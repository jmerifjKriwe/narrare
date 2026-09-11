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
    (BackendProfileProvider — loads ProjectWritingProfile from KB character
    entities, ADR-069 Phase 4 closure) + AdaptiveSettingsRepository
    (Phase 3 Task 4 — DB-backed).

    The ``BackendProfileProvider`` is bound to ``get_session_factory()``
    (not the request ``session``) so it mirrors the invocation-pipeline
    singleton wiring and opens its own short-lived read session per call.
    """
    from narrare._app.database import get_session_factory
    from narrare._app.dependencies import (
        _get_preference_service_instance,  # pyright: ignore[reportPrivateUsage]
    )
    from narrare.adaptive.adaptive_context_provider import (
        AdaptiveContextProviderImpl,
    )
    from narrare.adaptive.profile_provider_impl import BackendProfileProvider

    preference_service = _get_preference_service_instance()
    settings_repo = get_adaptive_settings_repository(session)
    return AdaptiveContextProviderImpl(
        preference_provider=preference_service,
        profile_provider=BackendProfileProvider(session_factory=get_session_factory()),
        settings_repo=settings_repo,
    )


def get_adaptive_context_service(
    session: SessionDep,
) -> AdaptiveContextService:
    """Create an AdaptiveContextService with production DI."""
    from narrare.adaptive.service import AdaptiveContextService
    from narrare.evidence.repository import EvidenceRepositoryImpl
    from narrare.novels.repository import NovelRepository

    provider = get_adaptive_context_provider(session)
    settings_repo = get_adaptive_settings_repository(session)
    evidence_repo = EvidenceRepositoryImpl(session)
    return AdaptiveContextService(
        provider=provider,
        settings_repo=settings_repo,
        evidence_repo=evidence_repo,
        novel_repo=NovelRepository(session),
    )
