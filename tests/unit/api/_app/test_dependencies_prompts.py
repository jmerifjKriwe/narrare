"""Unit tests for ``narrare._app.dependencies_prompts`` — preference service,
prompt registry, and prompt composer singletons.

Covers:
- ``_get_preference_service_instance()`` graceful-degradation paths
  (mem0 not installed, no credentials, NullMemoryClient)
- ``_get_preference_service_instance()`` success path
- ``_get_prompt_registry_instance()`` / ``get_registry()``
- ``_get_composer_instance()`` / ``get_composer()``
"""

from __future__ import annotations

from typing import Any

import pytest

import narrare._app.dependencies_prompts as prompts_mod
from narrare_core.memory._null_client import NullMemoryClient
from narrare_core.memory.availability import ProviderEnvConfig
from narrare_core.prompts import PromptComposer, PromptRegistry


@pytest.fixture(autouse=True)
def _reset_preference_state() -> Any:  # pyright: ignore[reportUnusedFunction]
    """Reset module-level singleton state between tests."""
    original_instance = prompts_mod._preference_service_instance
    original_tried = prompts_mod._preference_service_init_tried
    prompts_mod._preference_service_instance = None
    prompts_mod._preference_service_init_tried = False
    yield
    prompts_mod._preference_service_instance = original_instance
    prompts_mod._preference_service_init_tried = original_tried


def _provider_config() -> ProviderEnvConfig:
    """A stand-in provider config for testing."""
    return ProviderEnvConfig(provider="openai", api_key="test-key", base_url=None)


# ---------------------------------------------------------------------------
# Preference service — disabled paths
# ---------------------------------------------------------------------------


class TestPreferenceServiceDisabled:
    def test_returns_none_when_mem0_not_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When mem0 is not installed, preference service is disabled."""
        monkeypatch.setattr(
            "narrare._app.dependencies_prompts.is_mem0_available",
            lambda: False,
        )

        result = prompts_mod._get_preference_service_instance()

        assert result is None

    def test_returns_none_when_no_provider_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When provider detection returns None, service is disabled."""
        monkeypatch.setattr(
            "narrare._app.dependencies_prompts.is_mem0_available",
            lambda: True,
        )
        monkeypatch.setattr(
            "narrare._app.dependencies_prompts.detect_provider_from_env",
            lambda: None,
        )

        result = prompts_mod._get_preference_service_instance()

        assert result is None

    def test_caches_result_after_first_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """After first call, _preference_service_init_tried prevents re-init."""
        monkeypatch.setattr(
            "narrare._app.dependencies_prompts.is_mem0_available",
            lambda: False,
        )

        first = prompts_mod._get_preference_service_instance()
        assert first is None
        assert prompts_mod._preference_service_init_tried is True

        # Second call should return cached None without re-checking
        second = prompts_mod._get_preference_service_instance()
        assert second is None


# ---------------------------------------------------------------------------
# Preference service — NullMemoryClient path
# ---------------------------------------------------------------------------


class TestPreferenceServiceNullClient:
    def test_returns_none_when_client_is_null(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NullMemoryClient from create_memory_client_sync disables the service."""
        monkeypatch.setattr(
            "narrare._app.dependencies_prompts.is_mem0_available",
            lambda: True,
        )
        monkeypatch.setattr(
            "narrare._app.dependencies_prompts.detect_provider_from_env",
            _provider_config,
        )
        monkeypatch.setattr(
            "narrare_core.memory.mem0_client.create_memory_client_sync",
            lambda **_kw: NullMemoryClient(),
        )

        result = prompts_mod._get_preference_service_instance()

        assert result is None


# ---------------------------------------------------------------------------
# Preference service — success path
# ---------------------------------------------------------------------------


class _FakePreferenceService:
    """Stand-in for PreferenceService."""

    pass


class TestPreferenceServiceSuccess:
    def test_creates_service_when_client_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When mem0 + credentials + valid client, PreferenceService is created."""
        monkeypatch.setattr(
            "narrare._app.dependencies_prompts.is_mem0_available",
            lambda: True,
        )
        monkeypatch.setattr(
            "narrare._app.dependencies_prompts.detect_provider_from_env",
            _provider_config,
        )
        monkeypatch.setattr(
            "narrare_core.memory.mem0_client.create_memory_client_sync",
            lambda **_kw: object(),  # non-NullMemoryClient
        )
        monkeypatch.setattr(
            "narrare_core.memory.preference_service.PreferenceService",
            lambda mem0_client: _FakePreferenceService(),
        )

        result = prompts_mod._get_preference_service_instance()

        assert result is not None
        assert isinstance(result, _FakePreferenceService)


# ---------------------------------------------------------------------------
# Preference service — E2E stub path (dependencies_prompts.py:111)
# ---------------------------------------------------------------------------


class TestPreferenceServiceE2EStub:
    def test_e2e_mode_keeps_null_client_wrapped_in_service(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """E2E mode: NullMemoryClient stays active inside a PreferenceService.

        With ``e2e_test=True`` the null client is an intentional stub — the
        service is still created (logging ``preference_service_e2e_stub_active``)
        so the preference path runs its normal code path instead of being
        skipped.
        """
        from structlog.testing import capture_logs

        class _E2ECoreSettings:
            e2e_test = True

        monkeypatch.setattr(
            "narrare._app.dependencies_prompts.is_mem0_available",
            lambda: True,
        )
        monkeypatch.setattr(
            "narrare._app.dependencies_prompts.detect_provider_from_env",
            _provider_config,
        )
        monkeypatch.setattr(
            "narrare_core.memory.mem0_client.create_memory_client_sync",
            lambda **_kw: NullMemoryClient(),
        )
        monkeypatch.setattr(
            "narrare._app.dependencies_prompts.get_core_settings",
            lambda: _E2ECoreSettings(),
        )
        monkeypatch.setattr(
            "narrare_core.memory.preference_service.PreferenceService",
            lambda mem0_client: _FakePreferenceService(),
        )

        with capture_logs() as logs:
            result = prompts_mod._get_preference_service_instance()

        assert result is not None
        assert isinstance(result, _FakePreferenceService)
        assert any(log.get("event") == "preference_service_e2e_stub_active" for log in logs)


# ---------------------------------------------------------------------------
# Prompt Registry singleton
# ---------------------------------------------------------------------------


class TestPromptRegistry:
    def test_get_registry_returns_prompt_registry(self) -> None:
        """get_registry() returns a PromptRegistry instance."""
        prompts_mod._get_prompt_registry_instance.cache_clear()

        registry = prompts_mod.get_registry()

        assert isinstance(registry, PromptRegistry)

    def test_registry_cached_on_repeated_calls(self) -> None:
        """@lru_cache returns the same instance on second call."""
        prompts_mod._get_prompt_registry_instance.cache_clear()

        first = prompts_mod.get_registry()
        second = prompts_mod.get_registry()

        assert first is second


# ---------------------------------------------------------------------------
# Prompt Composer singleton
# ---------------------------------------------------------------------------


class TestPromptComposer:
    def test_get_composer_returns_prompt_composer(self) -> None:
        """get_composer() returns a PromptComposer instance."""
        prompts_mod._get_composer_instance.cache_clear()

        composer = prompts_mod.get_composer()

        assert isinstance(composer, PromptComposer)

    def test_composer_cached_on_repeated_calls(self) -> None:
        """@lru_cache returns the same instance on second call."""
        prompts_mod._get_composer_instance.cache_clear()

        first = prompts_mod.get_composer()
        second = prompts_mod.get_composer()

        assert first is second


# ---------------------------------------------------------------------------
# Regression: no real mem0/Qdrant clients in unit tests (RULE-20)
# ---------------------------------------------------------------------------


class TestNoRealMem0InUnitTests:
    """Regression guard: unit tests must never create real mem0 clients.

    Bug history: ``TestPromptComposer`` and ``TestGetInvocationPipeline``
    called ``get_composer()`` / ``get_invocation_pipeline()`` without
    mocking the preference-service DI path. Since mem0 IS installed in
    the test environment and ``conftest.py`` sets dummy ``OPENAI_API_KEY``
    / ``ANTHROPIC_API_KEY``, ``_get_preference_service_instance()``
    reached ``create_memory_client_sync()`` and created real
    ``AsyncMemory`` instances backed by local Qdrant. This leaked:

    - ``~/.mem0/migrations_qdrant/.lock``  (file handle)
    - ``/tmp/qdrant/.lock``                (file handle)
    - sqlite connections                   (mem0 history store)
    - QdrantClient ``__del__`` tracebacks at interpreter shutdown
      (``ImportError: sys.meta_path is None, Python is likely shutting down``)

    Root cause: ``is_mem0_available()`` returned ``True`` in unit tests.

    Fix: ``tests/unit/conftest.py`` mocks ``is_mem0_available`` to
    ``False`` so ``_get_preference_service_instance()`` short-circuits
    before reaching ``create_memory_client_sync()``.
    """

    def test_get_composer_does_not_call_create_memory_client_sync(self) -> None:
        """get_composer() must not trigger real mem0 client creation.

        Spies on ``create_memory_client_sync`` — if the preference-service
        DI path is not properly isolated, this spy fires.
        """
        from unittest.mock import patch

        # Reset singleton + clear lru_cache so the spy observes a fresh
        # composer assembly (not a cached result from an earlier test).
        prompts_mod._preference_service_instance = None
        prompts_mod._preference_service_init_tried = False
        prompts_mod._get_composer_instance.cache_clear()

        with patch("narrare_core.memory.mem0_client.create_memory_client_sync") as spy_create:
            prompts_mod.get_composer()

        assert not spy_create.called, (
            "get_composer() triggered create_memory_client_sync() — "
            "a real mem0/Qdrant client would be created. "
            "Unit tests must never create real external resources (RULE-20). "
            "Ensure tests/unit/conftest.py mocks is_mem0_available() to False."
        )
