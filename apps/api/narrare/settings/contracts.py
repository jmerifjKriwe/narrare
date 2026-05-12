"""Settings service contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.settings.models import ProjectSettings, UserSettings
    from narrare.settings.schemas import (
        UpdateProjectSettingsRequest,
        UpdateUserSettingsRequest,
    )


@runtime_checkable
class UserSettingsRepositoryProtocol(Protocol):
    async def get(self, user_id: uuid.UUID) -> UserSettings: ...

    async def update(
        self, user_id: uuid.UUID, request: UpdateUserSettingsRequest
    ) -> UserSettings: ...


@runtime_checkable
class ProjectSettingsRepositoryProtocol(Protocol):
    async def get(self, novel_id: uuid.UUID) -> ProjectSettings: ...

    async def update(
        self, novel_id: uuid.UUID, request: UpdateProjectSettingsRequest
    ) -> ProjectSettings: ...
