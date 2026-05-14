"""AI settings service contracts.

Defines Protocol classes for AI-related repository and service interfaces.
Split from contracts.py for RULE-04 compliance.

Covers:
- User provider management (API key storage, encryption)
- User-level AI settings (default model, category/intent overrides)
- Project-level AI overrides
- Model routing cascade resolution
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.settings.models import (
        ProjectSettings,
        UserAiSettings,
        UserProvider,
    )
    from narrare.settings.schemas import (
        CreateProviderRequest,
        ProjectAiSettingsResponse,
        ProviderResponse,
        UpdateProjectAiSettingsRequest,
        UpdateProviderRequest,
        UpdateUserAiSettingsRequest,
        UserAiSettingsResponse,
    )


# ---------------------------------------------------------------------------
# Repository Protocols — AI settings (Tasks 6.1-6.3)
# ---------------------------------------------------------------------------


@runtime_checkable
class UserProvidersRepositoryProtocol(Protocol):
    """Repository for CRUD operations on user AI provider entries."""

    async def create(
        self,
        user_id: uuid.UUID,
        provider_name: str,
        api_key_encrypted: str,
        base_url: str | None,
    ) -> UserProvider:
        """Create a new provider entry for a user."""
        ...

    async def get(self, provider_id: uuid.UUID) -> UserProvider | None:
        """Get a provider by ID. Returns None if not found."""
        ...

    async def get_by_user(self, user_id: uuid.UUID) -> list[UserProvider]:
        """List all providers for a user (including inactive)."""
        ...

    async def update(self, provider_id: uuid.UUID, **kwargs: object) -> UserProvider:
        """Update provider fields. Raises if not found."""
        ...

    async def delete(self, provider_id: uuid.UUID) -> None:
        """Permanently delete a provider entry."""
        ...

    async def get_active(self, user_id: uuid.UUID) -> list[UserProvider]:
        """List active providers for a user."""
        ...


@runtime_checkable
class UserAiSettingsRepositoryProtocol(Protocol):
    """Repository for user-level AI settings (default model, overrides)."""

    async def get(self, user_id: uuid.UUID) -> UserAiSettings:
        """Get AI settings for a user. Auto-creates if missing."""
        ...

    async def update(self, user_id: uuid.UUID, **kwargs: object) -> UserAiSettings:
        """Update AI settings fields."""
        ...


@runtime_checkable
class ProjectAiSettingsRepositoryProtocol(Protocol):
    """Repository for project-level AI override settings."""

    async def get(self, novel_id: uuid.UUID) -> ProjectSettings:
        """Get project settings including AI override columns."""
        ...

    async def update(self, novel_id: uuid.UUID, **kwargs: object) -> ProjectSettings:
        """Update project AI override fields."""
        ...


# ---------------------------------------------------------------------------
# Service Protocols (Task 6.4)
# ---------------------------------------------------------------------------


@runtime_checkable
class UserProvidersServiceProtocol(Protocol):
    """Service for managing user AI providers with encryption."""

    async def create_provider(
        self,
        user_id: uuid.UUID,
        request: CreateProviderRequest,
    ) -> ProviderResponse:
        """Register a new AI provider for a user."""
        ...

    async def list_providers(
        self,
        user_id: uuid.UUID,
    ) -> list[ProviderResponse]:
        """List all providers for a user (masked API keys)."""
        ...

    async def update_provider(
        self,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
        request: UpdateProviderRequest,
    ) -> ProviderResponse:
        """Update provider credentials or status."""
        ...

    async def delete_provider(
        self,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """Delete a provider. Clears references from settings."""
        ...


@runtime_checkable
class UserAiSettingsServiceProtocol(Protocol):
    """Service for managing user-level AI settings."""

    async def get_settings(
        self,
        user_id: uuid.UUID,
    ) -> UserAiSettingsResponse:
        """Get user AI settings."""
        ...

    async def update_settings(
        self,
        user_id: uuid.UUID,
        request: UpdateUserAiSettingsRequest,
    ) -> UserAiSettingsResponse:
        """Update user AI settings. Validates provider references."""
        ...


@runtime_checkable
class ProjectAiSettingsServiceProtocol(Protocol):
    """Service for managing project-level AI overrides."""

    async def get_settings(
        self,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> ProjectAiSettingsResponse:
        """Get project AI settings."""
        ...

    async def update_settings(
        self,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
        request: UpdateProjectAiSettingsRequest,
    ) -> ProjectAiSettingsResponse:
        """Update project AI overrides."""
        ...
