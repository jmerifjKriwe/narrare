"""Unit tests for TokenLimitsService — three-layer resolution cascade."""

from __future__ import annotations

from narrare.settings.token_limits.contracts import TokenLimitOverrides
from narrare.settings.token_limits.models import ProjectTokenLimits, UserTokenLimits
from narrare.settings.token_limits.service import TokenLimitsService

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeUserRepo:
    def __init__(self, overrides: dict[str, object] | None = None) -> None:
        self._overrides = overrides or {}

    async def get(self, user_id: str) -> object:
        from unittest.mock import MagicMock

        m = MagicMock(spec=UserTokenLimits)
        m.overrides = self._overrides
        return m

    async def update(self, user_id: str, overrides: dict[str, object]) -> None:
        self._overrides.update(overrides)


class _FakeProjectRepo:
    def __init__(self, overrides: dict[str, object] | None = None) -> None:
        self._overrides = overrides or {}

    async def get(self, project_id: str) -> object:
        from unittest.mock import MagicMock

        m = MagicMock(spec=ProjectTokenLimits)
        m.overrides = self._overrides
        return m

    async def update(self, project_id: str, overrides: dict[str, object]) -> None:
        self._overrides.update(overrides)


class _FakeConfig:
    default_max_tokens = 4096
    ws_idle_timeout_seconds = 1800
    consistency_max_chapter_tokens = 2000
    consistency_max_kb_entries = 100
    default_max_selection_words = 2000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(
    *,
    user_overrides: dict[str, object] | None = None,
    project_overrides: dict[str, object] | None = None,
) -> TokenLimitsService:
    return TokenLimitsService(
        user_repo=_FakeUserRepo(user_overrides),  # type: ignore[arg-type]
        project_repo=_FakeProjectRepo(project_overrides),  # type: ignore[arg-type]
        config=_FakeConfig(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Tests: get_resolved_limits
# ---------------------------------------------------------------------------


class TestGetResolvedLimits:
    async def test_returns_defaults_with_no_overrides(self) -> None:
        service = _make_service()
        result = await service.get_resolved_limits(user_id="user1")
        assert isinstance(result, TokenLimitOverrides)
        assert result.output_limit == 4096

    async def test_project_overrides_applied(self) -> None:
        service = _make_service(project_overrides={"output_limit": 8192})
        result = await service.get_resolved_limits(user_id="user1", project_id="proj1")
        assert result.output_limit == 8192

    async def test_user_overrides_override_project(self) -> None:
        service = _make_service(
            project_overrides={"output_limit": 8192},
            user_overrides={"output_limit": 2048},
        )
        result = await service.get_resolved_limits(user_id="user1", project_id="proj1")
        assert result.output_limit == 2048

    async def test_user_overrides_without_project(self) -> None:
        service = _make_service(user_overrides={"ws_timeout": 900})
        result = await service.get_resolved_limits(user_id="user1")
        assert result.ws_timeout == 900

    async def test_no_project_id_skips_project_layer(self) -> None:
        service = _make_service(project_overrides={"output_limit": 8192})
        result = await service.get_resolved_limits(user_id="user1", project_id=None)
        # Project overrides should NOT be applied since project_id is None
        assert result.output_limit == 4096


# ---------------------------------------------------------------------------
# Tests: update_user_limits
# ---------------------------------------------------------------------------


class TestUpdateUserLimits:
    async def test_valid_field_updates(self) -> None:
        service = _make_service()
        await service.update_user_limits("user1", {"output_limit": 8192})

    async def test_invalid_field_raises(self) -> None:
        service = _make_service()
        try:
            await service.update_user_limits("user1", {"nonexistent_field": 999})
            raise AssertionError("Should have raised")
        except Exception as exc:
            assert "Unknown" in str(exc)

    async def test_invalid_profile_raises(self) -> None:
        service = _make_service()
        try:
            await service.update_user_limits("user1", {"token_profile": "invalid_profile"})
            raise AssertionError("Should have raised")
        except Exception as exc:
            assert "Invalid token profile" in str(exc)


class TestUpdateProjectLimits:
    async def test_valid_field_updates(self) -> None:
        service = _make_service()
        await service.update_project_limits("proj1", {"output_limit": 4096})

    async def test_invalid_field_raises(self) -> None:
        service = _make_service()
        try:
            await service.update_project_limits("proj1", {"bogus": True})
            raise AssertionError("Should have raised")
        except Exception as exc:
            assert "Unknown" in str(exc)
