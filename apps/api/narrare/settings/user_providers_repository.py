"""User providers repository — CRUD for user AI provider entries.

This repository handles ONLY database queries for the ``user_providers``
table. Business logic (encryption, validation) lives in the service layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from narrare._app.base_repository import BaseRepository
from narrare.settings.models import UserProvider

if TYPE_CHECKING:
    import uuid


class UserProvidersRepository(BaseRepository):
    """Repository for ``user_providers`` table operations."""

    async def create(
        self,
        user_id: uuid.UUID,
        provider_name: str,
        api_key_encrypted: str,
        base_url: str | None,
    ) -> UserProvider:
        """Create a new provider entry for a user.

        Args:
            user_id: Owner of the provider.
            provider_name: Provider identifier (e.g. "anthropic").
            api_key_encrypted: Already-encrypted API key.
            base_url: Optional custom base URL.

        Returns:
            The newly created ``UserProvider``.
        """
        provider = UserProvider(
            user_id=user_id,
            provider_name=provider_name,
            api_key_encrypted=api_key_encrypted,
            base_url=base_url,
        )
        self._session.add(provider)
        await self._flush_and_refresh(provider)
        return provider

    async def get(self, provider_id: uuid.UUID) -> UserProvider | None:
        """Get a provider by ID.

        Args:
            provider_id: The provider's UUID.

        Returns:
            The provider, or ``None`` if not found.
        """
        result = await self._session.execute(
            select(UserProvider).where(UserProvider.id == provider_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: uuid.UUID) -> list[UserProvider]:
        """List all providers for a user (including inactive).

        Args:
            user_id: The user's UUID.

        Returns:
            All provider entries for this user.
        """
        result = await self._session.execute(
            select(UserProvider)
            .where(UserProvider.user_id == user_id)
            .order_by(UserProvider.created_at)
        )
        return list(result.scalars().all())

    async def update(self, provider_id: uuid.UUID, **kwargs: object) -> UserProvider:
        """Update provider fields.

        Args:
            provider_id: The provider to update.
            **kwargs: Fields to update (api_key_encrypted, base_url, is_active).

        Returns:
            The updated provider.

        Raises:
            ValueError: If the provider is not found.
        """
        provider = await self.get(provider_id)
        if provider is None:
            raise ValueError(f"Provider {provider_id} not found")
        for field, value in kwargs.items():
            setattr(provider, field, value)
        await self._flush_and_refresh(provider)
        return provider

    async def delete(self, provider_id: uuid.UUID) -> None:
        """Permanently delete a provider entry.

        Args:
            provider_id: The provider to delete.
        """
        provider = await self.get(provider_id)
        if provider is not None:
            await self._session.delete(provider)
            await self._flush()

    async def get_active(self, user_id: uuid.UUID) -> list[UserProvider]:
        """List active providers for a user.

        Args:
            user_id: The user's UUID.

        Returns:
            Active provider entries for this user.
        """
        result = await self._session.execute(
            select(UserProvider)
            .where(UserProvider.user_id == user_id, UserProvider.is_active.is_(True))
            .order_by(UserProvider.created_at)
        )
        return list(result.scalars().all())

    async def get_by_name(self, user_id: uuid.UUID, provider_name: str) -> UserProvider | None:
        """Get a specific provider by user and provider name.

        Args:
            user_id: The user's UUID.
            provider_name: The provider identifier.

        Returns:
            The provider, or ``None`` if not found.
        """
        result = await self._session.execute(
            select(UserProvider).where(
                UserProvider.user_id == user_id,
                UserProvider.provider_name == provider_name,
            )
        )
        return result.scalar_one_or_none()
