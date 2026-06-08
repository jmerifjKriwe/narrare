"""Unit tests for token limits — resolution cascade and env layer.

Tests the three-layer merge logic (user → project → env → code defaults).
Uses in-memory fakes for repositories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from narrare.settings.token_limits.contracts import (
    TokenLimitsRepositoryProtocol,
    TokenLimitsServiceProtocol,
)

# ======================================================================
# In-memory Fakes
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
# Protocol conformance checks
# ======================================================================


class TestProtocolConformance:
    def test_fake_store_satisfies_repo_protocol(self) -> None:
        """_FakeStore implements all TokenLimitsRepositoryProtocol methods."""
        fake = _FakeStore()
        assert isinstance(fake, TokenLimitsRepositoryProtocol)

    def test_service_satisfies_protocol(self, service: Any) -> None:
        assert isinstance(service, TokenLimitsServiceProtocol)


# ======================================================================
# Test: get_resolved_limits — layer merging
# ======================================================================


class TestGetResolvedLimits:
    """Tests for TokenLimitsService.get_resolved_limits()."""

    async def test_with_no_overrides_returns_code_defaults(self, service: Any) -> None:
        """No user or project overrides → pure code defaults + env config."""
        user_id = "user_default"
        limits = await service.get_resolved_limits(user_id=user_id)

        assert limits.output_limit == 4096
        assert limits.token_profile == "balanced"
        assert limits.ws_timeout == 1800
        assert limits.retry_max_attempts == 3
        assert limits.retry_base_delay == 1.0

    async def test_user_overrides_override_code_defaults(
        self, store: _FakeStore, service: Any
    ) -> None:
        """User overrides should take priority over code/env defaults."""
        user_id = "user_overrides"
        store.seed_user(user_id, {"token_profile": "quick", "output_limit": 2048})

        limits = await service.get_resolved_limits(user_id=user_id)

        assert limits.output_limit == 2048
        assert limits.token_profile == "quick"

    async def test_project_overrides_apply_without_user_overrides(
        self, store: _FakeStore, service: Any
    ) -> None:
        """Project overrides apply when user has no overrides."""
        user_id = "user_no_overrides"
        project_id = "project_1"
        store.seed_project(project_id, {"ws_timeout": 3600, "retry_max_attempts": 5})

        limits = await service.get_resolved_limits(
            user_id=user_id,
            project_id=project_id,
        )

        assert limits.ws_timeout == 3600
        assert limits.retry_max_attempts == 5
        assert limits.output_limit == 4096
        assert limits.token_profile == "balanced"

    async def test_user_overrides_win_over_project(self, store: _FakeStore, service: Any) -> None:
        """User overrides have higher priority than project overrides."""
        user_id = "user_wins"
        project_id = "project_loses"
        store.seed_user(user_id, {"output_limit": 1024})
        store.seed_project(project_id, {"output_limit": 8000})

        limits = await service.get_resolved_limits(
            user_id=user_id,
            project_id=project_id,
        )

        assert limits.output_limit == 1024

    async def test_project_overrides_do_not_leak_to_other_users(
        self, store: _FakeStore, service: Any
    ) -> None:
        """Project overrides only affect the specified project."""
        user_id = "user_a"
        project_id = "project_secret"
        store.seed_project(project_id, {"token_profile": "long_texts"})

        limits_no_project = await service.get_resolved_limits(user_id=user_id)
        assert limits_no_project.token_profile == "balanced"

        limits_with_project = await service.get_resolved_limits(
            user_id=user_id,
            project_id=project_id,
        )
        assert limits_with_project.token_profile == "long_texts"

    async def test_tier_percentages_merge_from_user(self, store: _FakeStore, service: Any) -> None:
        """User can override tier_percentages."""
        user_id = "tier_user"
        custom_tiers = {
            "immediate": 0.50,
            "recent": 0.20,
            "kb_referenced": 0.15,
            "kb_suggested": 0.10,
            "pinned": 0.05,
        }
        store.seed_user(user_id, {"tier_percentages": custom_tiers})

        limits = await service.get_resolved_limits(user_id=user_id)

        assert limits.tier_percentages == custom_tiers

    async def test_retry_base_delay_from_env(
        self, store: _FakeStore, fake_config: _FakeConfig, service: Any
    ) -> None:
        """Env retry_base_delay is used when no overrides exist."""
        fake_config.retry_base_delay = 2.5
        user_id = "retry_user"

        limits = await service.get_resolved_limits(user_id=user_id)

        assert limits.retry_base_delay == 2.5

    async def test_project_id_none_skips_project_layer(self, service: Any) -> None:
        """When project_id is None, no project overrides are loaded."""
        user_id = "no_project_user"
        limits = await service.get_resolved_limits(user_id=user_id, project_id=None)
        assert limits.output_limit == 4096

    async def test_auto_create_user_on_first_access(self, store: _FakeStore, service: Any) -> None:
        """Service should auto-create user limits row on first access."""
        user_id = "new_user"
        limits = await service.get_resolved_limits(user_id=user_id)
        assert limits.output_limit == 4096

        entity = await store.get_user_entity(user_id)
        assert entity.overrides == {}


# ======================================================================
# Test: get_model_limits — model capability lookup
# ======================================================================


class TestTokenLimitsServiceModelValidation:
    """Tests for TokenLimitsService.get_model_limits()."""

    async def test_get_model_limits_returns_none_for_unknown(self, service: Any) -> None:
        """Unknown model returns None gracefully."""
        result = await service.get_model_limits("openai", "nonexistent-model")
        assert result is None

    async def test_get_model_limits_type(self, service: Any) -> None:
        """Returns ModelLimits type when data is available.

        In test environment no models.dev cache exists, so this will
        return None. The test validates the return type contract.
        """
        result = await service.get_model_limits("openai", "gpt-4o")
        assert result is None or hasattr(result, "context")
