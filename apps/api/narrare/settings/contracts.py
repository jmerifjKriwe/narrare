"""Settings service contracts.

Defines Protocol classes for repository interfaces in the
settings module. Contracts MUST exist before implementation (RULE-03).

Existing (Task 6.5) repository protocols for user and project settings.
For AI-related protocols, see contracts_ai.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.settings.models import (
        ProjectSettings,
        UserSettings,
    )
    from narrare.settings.schemas import (
        UpdateProjectSettingsRequest,
        UpdateUserSettingsRequest,
    )


# ---------------------------------------------------------------------------
# Repository Protocols - existing (Task 6.5: keep as-is)
# ---------------------------------------------------------------------------


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
