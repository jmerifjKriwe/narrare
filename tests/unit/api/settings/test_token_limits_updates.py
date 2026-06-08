"""Unit tests for token limits — update operations.

Tests user and project update endpoints including validation.
Uses in-memory fakes for repositories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from narrare_core.shared.errors import ValidationError

# ======================================================================
# In-memory Fakes (duplicated from test_token_limits_resolution.py)
# ======================================================================


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
    retry_max_attempts: int = 3
    retry_base_delay: float = 1.0
    consistency_max_chapter_tokens: int = 2000
    consistency_max_kb_entries: int = 100


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


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def store() -> _FakeStore:
    return _FakeStore()


@pytest.fixture
def fake_config() -> _FakeConfig:
    return _FakeConfig()


@pytest.fixture
def service(store: _FakeStore, fake_config: _FakeConfig) -> Any:
    """Create a TokenLimitsService with fake dependencies."""
    from narrare.settings.token_limits.service import TokenLimitsService

    return TokenLimitsService(
        user_repo=_FakeUserRepo(store.users),  # pyright: ignore[reportArgumentType]
        project_repo=_FakeProjectRepo(store.projects),  # pyright: ignore[reportArgumentType]
        config=fake_config,  # pyright: ignore[reportArgumentType]
    )


# ======================================================================
# Test: update_user_limits
# ======================================================================


class TestUpdateUserLimits:
    async def test_update_user_limits_persists(self, store: _FakeStore, service: Any) -> None:
        """Updating user limits should persist to the store."""
        user_id = "update_user"
        await service.update_user_limits(
            user_id,
            {"output_limit": 8192, "token_profile": "long_texts"},
        )

        entity = await store.get_user_entity(user_id)
        assert entity.overrides.get("output_limit") == 8192
        assert entity.overrides.get("token_profile") == "long_texts"

    async def test_update_user_limits_partial_merge(self, store: _FakeStore, service: Any) -> None:
        """Partial updates should merge with existing overrides."""
        user_id = "partial_user"
        store.seed_user(user_id, {"output_limit": 2048, "ws_timeout": 900})

        await service.update_user_limits(user_id, {"output_limit": 4096})

        entity = await store.get_user_entity(user_id)
        assert entity.overrides.get("output_limit") == 4096
        assert entity.overrides.get("ws_timeout") == 900

    async def test_update_user_limits_with_invalid_field_raises(self, service: Any) -> None:
        """Unknown field names should raise ValidationError."""
        with pytest.raises(ValidationError, match="Unknown token limit override"):
            await service.update_user_limits(
                "bad_user",
                {"nonexistent_field": 42},
            )

    async def test_update_user_limits_with_invalid_profile_raises(self, service: Any) -> None:
        """Invalid token_profile should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid token profile"):
            await service.update_user_limits(
                "bad_profile_user",
                {"token_profile": "ultra_fast"},
            )


# ======================================================================
# Test: update_project_limits
# ======================================================================


class TestUpdateProjectLimits:
    async def test_update_project_limits_persists(self, store: _FakeStore, service: Any) -> None:
        """Updating project limits should persist to the store."""
        project_id = "update_project"
        await service.update_project_limits(
            project_id,
            {"ws_timeout": 7200, "retry_max_attempts": 10},
        )

        entity = await store.get_project_entity(project_id)
        assert entity.overrides.get("ws_timeout") == 7200
        assert entity.overrides.get("retry_max_attempts") == 10

    async def test_update_project_limits_partial_merge(
        self, store: _FakeStore, service: Any
    ) -> None:
        """Partial updates should merge with existing overrides."""
        project_id = "partial_project"
        store.seed_project(project_id, {"output_limit": 1024})

        await service.update_project_limits(project_id, {"output_limit": 2048})

        entity = await store.get_project_entity(project_id)
        assert entity.overrides.get("output_limit") == 2048

    async def test_update_project_limits_with_invalid_field_raises(self, service: Any) -> None:
        """Unknown field names should raise ValidationError."""
        with pytest.raises(ValidationError, match="Unknown token limit override"):
            await service.update_project_limits(
                "bad_project",
                {"fake_field": "value"},
            )


# ======================================================================
# Test: env layer overrides code defaults
# ======================================================================


class TestEnvLayerOverrides:
    async def test_env_default_max_tokens_used(
        self, store: _FakeStore, fake_config: _FakeConfig, service: Any
    ) -> None:
        """Env default_max_tokens should override code default of 4096."""
        fake_config.default_max_tokens = 8192

        limits = await service.get_resolved_limits(user_id="env_test_user")

        assert limits.output_limit == 8192

    async def test_env_ws_timeout_used(
        self, store: _FakeStore, fake_config: _FakeConfig, service: Any
    ) -> None:
        """Env ws_idle_timeout_seconds should override code default."""
        fake_config.ws_idle_timeout_seconds = 3600

        limits = await service.get_resolved_limits(user_id="env_test_user")

        assert limits.ws_timeout == 3600

    async def test_user_overrides_env(
        self, store: _FakeStore, fake_config: _FakeConfig, service: Any
    ) -> None:
        """User overrides should still win over env config."""
        fake_config.default_max_tokens = 512
        fake_config.ws_idle_timeout_seconds = 600

        user_id = "user_beats_env"
        store.seed_user(user_id, {"output_limit": 4096, "ws_timeout": 1800})

        limits = await service.get_resolved_limits(user_id=user_id)

        assert limits.output_limit == 4096
        assert limits.ws_timeout == 1800
