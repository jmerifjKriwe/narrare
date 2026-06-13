"""Unit tests for token limits — router endpoint coverage.

Direct-call tests for get_resolved_limits, update_user_limits,
and update_project_limits endpoints. Uses Fake dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi import HTTPException

from narrare.settings.token_limits.models import UserTokenLimits
from narrare.settings.token_limits.router import (
    get_resolved_limits,
    update_project_limits,
    update_user_limits,
)
from narrare.settings.token_limits.schemas import (
    TokenLimitOverridesResponse,
    UpdateTokenLimitsRequest,
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
    default_max_selection_words: int = 2000


class _FakeUserRepo:
    """In-memory fake matching UserTokenLimitsRepository interface."""

    def __init__(self) -> None:
        self._store: dict[str, _FakeLimitsEntity] = {}

    async def get(self, user_id: str) -> UserTokenLimits:
        from unittest.mock import MagicMock

        entity = self._store.get(user_id)
        if not entity:
            entity = _FakeLimitsEntity(pk=user_id)
            self._store[user_id] = entity
        m = MagicMock(spec=UserTokenLimits)
        m.overrides = entity.overrides
        return m

    async def update(self, user_id: str, overrides: dict[str, object]) -> None:
        entity = self._store.get(user_id)
        if not entity:
            entity = _FakeLimitsEntity(pk=user_id)
            self._store[user_id] = entity
        entity.overrides.update(overrides)


class _FakeProjectRepo:
    """In-memory fake matching ProjectTokenLimitsRepository interface."""

    def __init__(self) -> None:
        self._store: dict[str, _FakeLimitsEntity] = {}

    async def get(self, project_id: str) -> object:
        entity = self._store.get(project_id)
        if not entity:
            entity = _FakeLimitsEntity(pk=project_id)
            self._store[project_id] = entity
        from unittest.mock import MagicMock

        m = MagicMock(spec=UserTokenLimits)
        m.overrides = entity.overrides
        return m

    async def update(self, project_id: str, overrides: dict[str, object]) -> None:
        entity = self._store.get(project_id)
        if not entity:
            entity = _FakeLimitsEntity(pk=project_id)
            self._store[project_id] = entity
        entity.overrides.update(overrides)


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def user_repo() -> _FakeUserRepo:
    return _FakeUserRepo()


@pytest.fixture
def project_repo() -> _FakeProjectRepo:
    return _FakeProjectRepo()


@pytest.fixture
def fake_config() -> _FakeConfig:
    return _FakeConfig()


@pytest.fixture
def service(user_repo, project_repo, fake_config):
    """Create a TokenLimitsService with fake dependencies."""
    from narrare.settings.token_limits.service import TokenLimitsService

    return TokenLimitsService(
        user_repo=user_repo,  # pyright: ignore[reportArgumentType]
        project_repo=project_repo,  # pyright: ignore[reportArgumentType]
        config=fake_config,  # pyright: ignore[reportArgumentType]
    )


# ======================================================================
# Tests: get_resolved_limits endpoint
# ======================================================================


class TestGetResolvedLimitsEndpoint:
    """Direct-call tests for the get_resolved_limits router endpoint."""

    async def test_get_resolved_limits_with_project_id(self, service) -> None:
        """When project_id is provided, the response includes resolved limits."""
        result = await get_resolved_limits(
            user_id="test_user",
            project_id="test_project",
            service=service,
        )

        assert isinstance(result, TokenLimitOverridesResponse)
        assert result.output_limit == 4096
        assert result.token_profile == "balanced"

    async def test_get_resolved_limits_without_project_id(self, service) -> None:
        """When project_id is None, project layer is skipped."""
        result = await get_resolved_limits(
            user_id="test_user",
            project_id=None,
            service=service,
        )

        assert isinstance(result, TokenLimitOverridesResponse)
        assert result.ws_timeout == 1800


# ======================================================================
# Tests: update_user_limits endpoint
# ======================================================================


class TestUpdateUserLimitsEndpoint:
    """Direct-call tests for the update_user_limits router endpoint."""

    async def test_update_user_limits_with_valid_data(self, service) -> None:
        """Valid update_user_limits call should succeed (204)."""
        result = await update_user_limits(
            request=UpdateTokenLimitsRequest(output_limit=8192),
            user_id="user_1",
            service=service,
        )

        assert result is None

    @pytest.mark.filterwarnings("ignore::DeprecationWarning")
    async def test_update_user_limits_with_empty_body_raises_422(self, service) -> None:
        """Empty request (all None fields) should raise HTTP 422."""
        with pytest.raises(HTTPException) as exc_info:
            await update_user_limits(
                request=UpdateTokenLimitsRequest(),
                user_id="user_bad",
                service=service,
            )

        assert exc_info.value.status_code == 422
        assert "At least one field" in str(exc_info.value.detail)


# ======================================================================
# Tests: update_project_limits endpoint
# ======================================================================


class TestUpdateProjectLimitsEndpoint:
    """Direct-call tests for the update_project_limits router endpoint."""

    async def test_update_project_limits_with_valid_data(self, service) -> None:
        """Valid update_project_limits call should succeed (204)."""
        result = await update_project_limits(
            project_id="project_1",
            request=UpdateTokenLimitsRequest(ws_timeout=3600),
            user_id="user_1",
            service=service,
        )

        assert result is None

    @pytest.mark.filterwarnings("ignore::DeprecationWarning")
    async def test_update_project_limits_with_empty_body_raises_422(self, service) -> None:
        """Empty request (all None fields) should raise HTTP 422."""
        with pytest.raises(HTTPException) as exc_info:
            await update_project_limits(
                project_id="project_bad",
                request=UpdateTokenLimitsRequest(),
                user_id="user_1",
                service=service,
            )

        assert exc_info.value.status_code == 422
        assert "At least one field" in str(exc_info.value.detail)
