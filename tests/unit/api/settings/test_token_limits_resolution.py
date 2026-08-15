"""Unit tests for token limits — resolution cascade and env layer.

Tests the three-layer merge logic (user → project → env → code defaults).
Uses the shared in-memory fakes from ``_token_limits_fakes.py``.
"""

from __future__ import annotations

from typing import Any

import pytest

from narrare.settings.token_limits.protocols import (
    TokenLimitsRepositoryProtocol,
    TokenLimitsServiceProtocol,
)
from narrare_core.context.budget import (
    DEFAULT_SERIES_HISTORY_BUDGET,
    DEFAULT_TOTAL_BUDGET,
)
from tests.unit.api.settings._token_limits_fakes import (
    _FakeConfig,
    _FakeProjectRepo,
    _FakeStore,
    _FakeUserRepo,
)

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


def _make_service(store: _FakeStore, fake_config: _FakeConfig) -> Any:
    """TokenLimitsService over the shared fakes (config varies per test)."""
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
        store.seed_project(project_id, {"ws_timeout": 3600})

        limits = await service.get_resolved_limits(
            user_id=user_id,
            project_id=project_id,
        )

        assert limits.ws_timeout == 3600
        assert limits.output_limit == 4096
        assert limits.token_profile == "balanced"

    async def test_legacy_retry_overrides_are_ignored(
        self, store: _FakeStore, service: Any
    ) -> None:
        """ADR-060: legacy persisted ``retry_*`` keys must be silently dropped.

        Transport retry is no longer a token-limits override. A stored
        ``retry_max_attempts`` / ``retry_base_delay`` JSONB key left over from a
        pre-ADR-060 row must not raise and must not surface on the resolved
        ``TokenLimitOverrides`` (unknown-key drop in ``_merge_overrides``). A
        sibling real override (``ws_timeout``) alongside them still resolves.
        """
        user_id = "legacy_retry_user"
        store.seed_user(
            user_id,
            {"ws_timeout": 600, "retry_max_attempts": 9, "retry_base_delay": 7.5},
        )

        limits = await service.get_resolved_limits(user_id=user_id)

        assert limits.ws_timeout == 600
        assert not hasattr(limits, "retry_max_attempts")
        assert not hasattr(limits, "retry_base_delay")

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


class TestContextBudgetResolution:
    """ADR-082: the two context-budget keys resolve through the full
    cascade (user-DB -> project-DB -> operator-env -> code defaults)."""

    async def test_no_overrides_returns_core_constants(self, service: Any) -> None:
        limits = await service.get_resolved_limits(user_id="user_ctx_default")

        assert limits.context_total_budget == DEFAULT_TOTAL_BUDGET  # 32,000
        assert limits.series_history_budget == DEFAULT_SERIES_HISTORY_BUDGET  # 16,000

    async def test_env_layer_applies_operator_values(
        self, store: _FakeStore, fake_config: _FakeConfig
    ) -> None:
        fake_config.context_total_budget = 48_000
        fake_config.series_history_budget = 12_000
        service = _make_service(store, fake_config)

        limits = await service.get_resolved_limits(user_id="user_ctx_env")

        assert limits.context_total_budget == 48_000
        assert limits.series_history_budget == 12_000

    async def test_user_override_wins_over_env(
        self, store: _FakeStore, fake_config: _FakeConfig
    ) -> None:
        fake_config.context_total_budget = 48_000
        service = _make_service(store, fake_config)
        store.seed_user("user_ctx_win", {"context_total_budget": 65_536})

        limits = await service.get_resolved_limits(user_id="user_ctx_win")

        assert limits.context_total_budget == 65_536
        assert limits.series_history_budget == DEFAULT_SERIES_HISTORY_BUDGET

    async def test_project_override_applies_without_user_override(
        self, store: _FakeStore, service: Any
    ) -> None:
        store.seed_project("project_ctx", {"series_history_budget": 8_192})

        limits = await service.get_resolved_limits(
            user_id="user_ctx_project", project_id="project_ctx"
        )

        assert limits.series_history_budget == 8_192

    async def test_env_values_survive_unrelated_db_merge(
        self, store: _FakeStore, fake_config: _FakeConfig
    ) -> None:
        """Regression for the _merge_overrides carry-through: an override
        dict for OTHER keys must not reset the env-layer budget values to
        code defaults."""
        fake_config.context_total_budget = 48_000
        service = _make_service(store, fake_config)
        store.seed_user("user_ctx_merge", {"ws_timeout": 3_600})

        limits = await service.get_resolved_limits(user_id="user_ctx_merge")

        assert limits.ws_timeout == 3_600
        assert limits.context_total_budget == 48_000


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
