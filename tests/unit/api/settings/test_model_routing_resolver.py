"""Unit tests for ModelRoutingResolverImpl — cascade resolution logic.

Tests the 6-level cascade: project_intent → project_category → user_intent
→ user_category → user_default → ConfigurationError. All repositories
are faked — no DB, real decrypt patched.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import pytest

from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm import LLMIntent
from narrare_core.llm.intent_categories import INTENT_CATEGORY_MAP
from narrare_core.shared.errors import ConfigurationError

# ---------------------------------------------------------------------------
# Fake model objects
# ---------------------------------------------------------------------------


class FakeUserProvider:
    """Minimal fake UserProvider ORM object."""

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        provider_name: str = "anthropic",
        api_key_encrypted: str = "encrypted",
        base_url: str | None = None,
        is_active: bool = True,
    ) -> None:
        self.id = id or uuid.uuid4()
        self.user_id = user_id or uuid.uuid4()
        self.provider_name = provider_name
        self.api_key_encrypted = api_key_encrypted
        self.base_url = base_url
        self.is_active = is_active


class FakeProjectSettings:
    """Minimal fake ProjectSettings ORM object."""

    def __init__(
        self,
        *,
        intent_overrides: dict[str, object] | None = None,
        category_overrides: dict[str, object] | None = None,
    ) -> None:
        self.intent_overrides = intent_overrides or {}
        self.category_overrides = category_overrides or {}


class FakeUserAiSettings:
    """Minimal fake UserAiSettings ORM object."""

    def __init__(
        self,
        *,
        default_provider_id: uuid.UUID | None = None,
        default_model: str = "",
        intent_overrides: dict[str, object] | None = None,
        category_overrides: dict[str, object] | None = None,
    ) -> None:
        self.default_provider_id = default_provider_id
        self.default_model = default_model
        self.intent_overrides = intent_overrides or {}
        self.category_overrides = category_overrides or {}


# ---------------------------------------------------------------------------
# Fake repositories
# ---------------------------------------------------------------------------


class FakeProvidersRepo:
    def __init__(self) -> None:
        self._providers: dict[uuid.UUID, FakeUserProvider] = {}

    def seed(self, *providers: FakeUserProvider) -> None:
        for p in providers:
            self._providers[p.id] = p

    async def get(self, provider_id: uuid.UUID) -> FakeUserProvider | None:
        return self._providers.get(provider_id)


class FakeUserAiRepo:
    def __init__(self, settings: FakeUserAiSettings | None = None) -> None:
        self._settings = settings or FakeUserAiSettings()

    async def get(self, user_id: uuid.UUID) -> FakeUserAiSettings:
        return self._settings


class FakeProjectAiRepo:
    def __init__(self, settings: FakeProjectSettings | None = None) -> None:
        self._settings = settings or FakeProjectSettings()

    async def get(self, novel_id: uuid.UUID) -> FakeProjectSettings:
        return self._settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_resolver(
    *,
    providers_repo: FakeProvidersRepo | None = None,
    user_settings: FakeUserAiSettings | None = None,
    project_settings: FakeProjectSettings | None = None,
) -> ModelRoutingResolverImpl:
    """Create a resolver with faked repos."""
    return ModelRoutingResolverImpl(
        user_providers_repo=providers_repo or FakeProvidersRepo(),  # type: ignore[arg-type]
        user_ai_settings_repo=FakeUserAiRepo(user_settings),  # type: ignore[arg-type]
        project_ai_settings_repo=FakeProjectAiRepo(project_settings),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def project_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def provider_id() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResolveByIntentCategory:
    @patch.object(ModelRoutingResolverImpl, "_decrypt_key", return_value="decrypted-key")
    async def test_resolves_model_by_project_intent_override(
        self,
        mock_decrypt: Any,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        provider = FakeUserProvider(id=provider_id, user_id=user_id, provider_name="openai")
        providers_repo = FakeProvidersRepo()
        providers_repo.seed(provider)

        resolver = _make_resolver(
            providers_repo=providers_repo,
            user_settings=FakeUserAiSettings(),
            project_settings=FakeProjectSettings(
                intent_overrides={
                    "write": {"provider_id": str(provider_id), "model_id": "gpt-4o"},
                },
            ),
        )

        result = await resolver.resolve(LLMIntent.WRITE, user_id, project_id)

        assert result.config.provider_name == "openai"
        assert result.config.model_id == "gpt-4o"
        assert result.source == "project_intent"

    @patch.object(ModelRoutingResolverImpl, "_decrypt_key", return_value="decrypted-key")
    async def test_resolves_model_by_project_category_override(
        self,
        mock_decrypt: Any,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        provider = FakeUserProvider(id=provider_id, user_id=user_id, provider_name="anthropic")
        providers_repo = FakeProvidersRepo()
        providers_repo.seed(provider)

        category = INTENT_CATEGORY_MAP.get(LLMIntent.WRITE)
        assert category is not None

        resolver = _make_resolver(
            providers_repo=providers_repo,
            user_settings=FakeUserAiSettings(),
            project_settings=FakeProjectSettings(
                category_overrides={
                    category.value: {"provider_id": str(provider_id), "model_id": "claude-sonnet"},
                },
            ),
        )

        result = await resolver.resolve(LLMIntent.WRITE, user_id, project_id)

        assert result.config.provider_name == "anthropic"
        assert result.config.model_id == "claude-sonnet"
        assert result.source == "project_category"

    @patch.object(ModelRoutingResolverImpl, "_decrypt_key", return_value="decrypted-key")
    async def test_fallback_to_user_default_model(
        self,
        mock_decrypt: Any,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        provider = FakeUserProvider(id=provider_id, user_id=user_id, provider_name="openai")
        providers_repo = FakeProvidersRepo()
        providers_repo.seed(provider)

        resolver = _make_resolver(
            providers_repo=providers_repo,
            user_settings=FakeUserAiSettings(
                default_provider_id=provider_id,
                default_model="gpt-4o-mini",
            ),
            project_settings=FakeProjectSettings(),
        )

        result = await resolver.resolve(LLMIntent.WRITE, user_id, project_id)

        assert result.config.provider_name == "openai"
        assert result.config.model_id == "gpt-4o-mini"
        assert result.source == "user_default"

    @patch.object(ModelRoutingResolverImpl, "_decrypt_key", return_value="decrypted-key")
    async def test_override_applies_correctly_skips_lower_priority(
        self,
        mock_decrypt: Any,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        """User intent override takes precedence over user default."""
        provider = FakeUserProvider(id=provider_id, user_id=user_id, provider_name="anthropic")
        providers_repo = FakeProvidersRepo()
        providers_repo.seed(provider)

        resolver = _make_resolver(
            providers_repo=providers_repo,
            user_settings=FakeUserAiSettings(
                default_provider_id=provider_id,
                default_model="claude-haiku",
                intent_overrides={
                    "summarize": {"provider_id": str(provider_id), "model_id": "claude-sonnet"},
                },
            ),
            project_settings=FakeProjectSettings(),
        )

        result = await resolver.resolve(LLMIntent.SUMMARIZE, user_id, None)

        assert result.config.model_id == "claude-sonnet"
        assert result.source == "user_intent"


class TestResolveErrors:
    async def test_raises_configuration_error_when_no_provider(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> None:
        resolver = _make_resolver(
            user_settings=FakeUserAiSettings(),
            project_settings=FakeProjectSettings(),
        )

        with pytest.raises(ConfigurationError, match="No AI provider configured"):
            await resolver.resolve(LLMIntent.WRITE, user_id, project_id)

    @patch.object(ModelRoutingResolverImpl, "_decrypt_key", return_value="decrypted-key")
    async def test_skips_inactive_provider_in_override(
        self,
        mock_decrypt: Any,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> None:
        provider = FakeUserProvider(
            id=provider_id,
            user_id=user_id,
            provider_name="anthropic",
            is_active=False,
        )
        providers_repo = FakeProvidersRepo()
        providers_repo.seed(provider)

        resolver = _make_resolver(
            providers_repo=providers_repo,
            user_settings=FakeUserAiSettings(
                intent_overrides={
                    "write": {"provider_id": str(provider_id), "model_id": "claude-sonnet"},
                },
            ),
            project_settings=FakeProjectSettings(),
        )

        # Falls through to no-provider since override provider is inactive
        with pytest.raises(ConfigurationError):
            await resolver.resolve(LLMIntent.WRITE, user_id, None)


class TestDecryptKey:
    def test_decrypt_key_returns_none_for_empty(self) -> None:
        result = ModelRoutingResolverImpl._decrypt_key("")
        assert result is None

    @patch("narrare.settings.model_routing_resolver.decrypt", return_value="plaintext")
    def test_decrypt_key_returns_decrypted(self, mock_decrypt: Any) -> None:
        result = ModelRoutingResolverImpl._decrypt_key("encrypted_token")
        assert result == "plaintext"
        mock_decrypt.assert_called_once_with("encrypted_token")
