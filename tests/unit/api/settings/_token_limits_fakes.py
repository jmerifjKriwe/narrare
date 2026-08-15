"""In-memory fakes for token-limits resolution tests.

Shared fake surface for ``TokenLimitsService`` tests: a minimal
``Settings`` fake (``_FakeConfig``), the user/project repository fakes,
and the combined ``_FakeStore``. Extracted verbatim from
``test_token_limits_resolution.py`` for RULE-04 (file-size split,
C5 Task 2b — same pattern as ``_provider_fakes.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from narrare_core.context.budget import (
    DEFAULT_SERIES_HISTORY_BUDGET,
    DEFAULT_TOTAL_BUDGET,
)


@dataclass
class _FakeLimitsEntity:
    """Generic in-memory entity matching UserTokenLimits / ProjectTokenLimits."""

    pk: str
    overrides: dict[str, object] = field(default_factory=dict)


@dataclass
class _FakeConfig:
    """Minimal fake for Settings — only token limit fields."""

    default_max_tokens: int = 4096
    ws_idle_timeout_seconds: int = 1800
    consistency_max_chapter_tokens: int = 2000
    consistency_max_kb_entries: int = 100
    default_max_selection_words: int = 2000
    context_total_budget: int = DEFAULT_TOTAL_BUDGET
    series_history_budget: int = DEFAULT_SERIES_HISTORY_BUDGET


class _FakeUserRepo:
    """In-memory fake matching UserTokenLimitsRepository interface."""

    def __init__(self, store: dict[str, _FakeLimitsEntity]) -> None:
        self._store = store

    async def get(self, user_id: str) -> _FakeLimitsEntity:
        entity = self._store.get(user_id)
        if not entity:
            entity = _FakeLimitsEntity(pk=user_id)
            self._store[user_id] = entity
        return entity

    async def update(self, user_id: str, overrides: dict[str, object]) -> _FakeLimitsEntity:
        entity = await self.get(user_id)
        current = dict(entity.overrides)
        current.update(overrides)
        entity.overrides = current
        return entity


class _FakeProjectRepo:
    """In-memory fake matching ProjectTokenLimitsRepository interface."""

    def __init__(self, store: dict[str, _FakeLimitsEntity]) -> None:
        self._store = store

    async def get(self, project_id: str) -> _FakeLimitsEntity:
        entity = self._store.get(project_id)
        if not entity:
            entity = _FakeLimitsEntity(pk=project_id)
            self._store[project_id] = entity
        return entity

    async def update(self, project_id: str, overrides: dict[str, object]) -> _FakeLimitsEntity:
        entity = await self.get(project_id)
        current = dict(entity.overrides)
        current.update(overrides)
        entity.overrides = current
        return entity


@dataclass
class _FakeStore:
    """Shared state for user/project stores + helper methods.

    Implements TokenLimitsRepositoryProtocol methods so it satisfies
    the combined repository protocol for conformance testing.
    """

    users: dict[str, _FakeLimitsEntity] = field(default_factory=dict)
    projects: dict[str, _FakeLimitsEntity] = field(default_factory=dict)

    def seed_user(self, user_id: str, overrides: dict[str, object] | None = None) -> None:
        self.users[user_id] = _FakeLimitsEntity(pk=user_id, overrides=overrides or {})

    def seed_project(self, project_id: str, overrides: dict[str, object] | None = None) -> None:
        self.projects[project_id] = _FakeLimitsEntity(pk=project_id, overrides=overrides or {})

    async def get_user_entity(self, user_id: str) -> _FakeLimitsEntity:
        if user_id not in self.users:
            self.users[user_id] = _FakeLimitsEntity(pk=user_id)
        return self.users[user_id]

    async def get_project_entity(self, project_id: str) -> _FakeLimitsEntity:
        if project_id not in self.projects:
            self.projects[project_id] = _FakeLimitsEntity(pk=project_id)
        return self.projects[project_id]

    # -- TokenLimitsRepositoryProtocol method names --

    async def get_user_limits(self, user_id: str) -> _FakeLimitsEntity:
        return await self.get_user_entity(user_id)

    async def update_user_limits(
        self, user_id: str, overrides: dict[str, object]
    ) -> _FakeLimitsEntity:
        entity = await self.get_user_entity(user_id)
        current = dict(entity.overrides)
        current.update(overrides)
        entity.overrides = current
        return entity

    async def get_project_limits(self, project_id: str) -> _FakeLimitsEntity:
        return await self.get_project_entity(project_id)

    async def update_project_limits(
        self, project_id: str, overrides: dict[str, object]
    ) -> _FakeLimitsEntity:
        entity = await self.get_project_entity(project_id)
        current = dict(entity.overrides)
        current.update(overrides)
        entity.overrides = current
        return entity
