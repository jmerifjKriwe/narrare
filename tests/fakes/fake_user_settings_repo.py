"""Fake UserSettingsRepository for unit tests.

Implements UserSettingsRepositoryProtocol from contracts.py.
Stores settings in-memory with call recording.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.settings.models import UserSettings

if TYPE_CHECKING:
    import uuid

    from narrare.settings.schemas import UpdateUserSettingsRequest


class FakeUserSettingsRepository:
    """In-memory fake for UserSettingsRepository.

    Usage:
        repo = FakeUserSettingsRepository()
        repo.seed(user_id, custom_tones=[...])
        settings = await repo.get(user_id)
    """

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, UserSettings] = {}
        self.calls: list[dict[str, object]] = []

    def seed(
        self,
        user_id: uuid.UUID,
        custom_tones: list[dict[str, object]] | None = None,
    ) -> UserSettings:
        """Pre-populate settings for a user."""
        settings = UserSettings(
            user_id=user_id,
            display_name="Test User",
            ui_language="en",
            theme="system",
            custom_tones=custom_tones or [],
        )
        self._store[user_id] = settings
        return settings

    async def get(self, user_id: uuid.UUID) -> UserSettings:
        """Get settings, creating defaults if not found."""
        self.calls.append({"method": "get", "user_id": user_id})
        if user_id not in self._store:
            return self.seed(user_id)
        return self._store[user_id]

    async def update(self, user_id: uuid.UUID, request: UpdateUserSettingsRequest) -> UserSettings:
        """Update settings, applying only non-None fields."""
        self.calls.append({"method": "update", "user_id": user_id, "request": request})
        settings = await self.get(user_id)
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(settings, field, value)
        self._store[user_id] = settings
        return settings
