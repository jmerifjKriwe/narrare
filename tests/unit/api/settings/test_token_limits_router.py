"""Unit tests for token limits — router endpoint coverage.

Direct-call tests for get_resolved_limits, update_user_limits,
and update_project_limits endpoints. Uses Fake dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

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

    async def test_get_returns_default_tier_percentages_when_not_configured(self, service) -> None:
        """FIND-012: the API always returns a complete tier_percentages dict.

        The resolved ``TokenLimitOverrides.tier_percentages`` is ``None`` when
        no user/project override is configured (so the assembler preserves
        mode-specific allocations).  The public API must still present a
        complete distribution to the frontend.
        """
        from narrare.settings.token_limits.contracts import DEFAULT_TIER_PERCENTAGES

        # Fresh resolution → tier_percentages is None internally.
        result = await get_resolved_limits(
            user_id="unconfigured_user",
            project_id=None,
            service=service,
        )

        assert isinstance(result, TokenLimitOverridesResponse)
        assert result.tier_percentages == DEFAULT_TIER_PERCENTAGES
        assert sum(result.tier_percentages.values()) == pytest.approx(1.0)


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


# ======================================================================
# Tests: UpdateTokenLimitsRequest schema validation
# ======================================================================


class TestUpdateTokenLimitsRequestSchema:
    """Schema-level validation for UpdateTokenLimitsRequest.token_profile.

    CR-08 P1: the public vocabulary is exactly the five Core profiles
    (``quick``, ``balanced``, ``long_texts``, ``comprehensive``, ``custom``).
    The retired ``conservative`` alias is rejected on writes and normalised
    to ``balanced`` only at the read boundary.
    """

    @pytest.mark.parametrize(
        "profile",
        ["quick", "balanced", "long_texts", "comprehensive", "custom"],
    )
    def test_all_public_profiles_accepted(self, profile: str) -> None:
        """The schema must accept exactly the five public token profiles."""
        req = UpdateTokenLimitsRequest(token_profile=profile)
        assert req.token_profile == profile

    def test_conservative_alias_rejected(self) -> None:
        """The retired ``conservative`` alias must be rejected on writes."""
        with pytest.raises(ValidationError):
            UpdateTokenLimitsRequest(token_profile="conservative")

    def test_invalid_profile_rejected(self) -> None:
        """Unknown profiles must be rejected by the schema."""
        with pytest.raises(ValidationError):
            UpdateTokenLimitsRequest(token_profile="ultra_fast")
