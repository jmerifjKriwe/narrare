"""Tests for ModelRoutingResolver cascade - core priority and ordering tests.

Verifies the cascade priority:
    project_intent -> project_category -> user_intent -> user_category -> user_default
    -> ConfigurationError
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest

from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm import LLMIntent
from narrare_core.shared.errors import ConfigurationError

# ---------------------------------------------------------------------------
# Fake repository objects (lightweight, no DB)
# ---------------------------------------------------------------------------


@dataclass
class FakeProvider:
    """Mimics the UserProvider ORM object."""

    id: uuid.UUID
    user_id: uuid.UUID
    provider_name: str
    api_key_encrypted: str
    base_url: str | None = None
    is_active: bool = True


@dataclass
class FakeUserAiSettings:
    """Mimics the UserAiSettings ORM object."""

    user_id: uuid.UUID
    default_provider_id: uuid.UUID | None = None
    default_model: str = ""
    category_overrides: dict[str, Any] | None = None
    intent_overrides: dict[str, Any] | None = None
    token_limit_overrides: dict[str, Any] | None = None


@dataclass
class FakeProjectSettings:
    """Mimics the ProjectSettings ORM object."""

    novel_id: uuid.UUID
    category_overrides: dict[str, Any] | None = None
    intent_overrides: dict[str, Any] | None = None
    token_limit_overrides: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

USER_ID = uuid.uuid4()
PROJECT_ID = uuid.uuid4()
PROVIDER_ID = uuid.uuid4()

ENCRYPTION_KEY_ENV = "NARRARE_ENCRYPTION_KEY"


@pytest.fixture(autouse=True)
def _set_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """Ensure encryption key is available for decrypt in resolver."""
    from cryptography.fernet import Fernet

    monkeypatch.setenv(ENCRYPTION_KEY_ENV, Fernet.generate_key().decode())


def _make_provider(
    *,
    provider_id: uuid.UUID = PROVIDER_ID,
    user_id: uuid.UUID = USER_ID,
    provider_name: str = "anthropic",
    api_key_encrypted: str | None = None,
    base_url: str | None = None,
    is_active: bool = True,
) -> FakeProvider:
    if api_key_encrypted is None:
        from narrare_core.crypto import encrypt

        api_key_encrypted = encrypt("sk-test-key")
    return FakeProvider(
        id=provider_id,
        user_id=user_id,
        provider_name=provider_name,
        api_key_encrypted=api_key_encrypted,
        base_url=base_url,
        is_active=is_active,
    )


def _make_resolver(
    *,
    providers: list[FakeProvider] | None = None,
    user_settings: FakeUserAiSettings | None = None,
    project_settings: FakeProjectSettings | None = None,
) -> ModelRoutingResolverImpl:
    """Build a resolver with mocked repos."""

    _providers = providers or []
    _user_settings = user_settings or FakeUserAiSettings(user_id=USER_ID)
    _project_settings = project_settings or FakeProjectSettings(novel_id=PROJECT_ID)

    providers_repo = AsyncMock()
    providers_repo.get = AsyncMock(
        side_effect=lambda pid: next((p for p in _providers if p.id == pid), None)
    )

    user_ai_repo = AsyncMock()
    user_ai_repo.get = AsyncMock(return_value=_user_settings)

    project_ai_repo = AsyncMock()
    project_ai_repo.get = AsyncMock(return_value=_project_settings)

    return ModelRoutingResolverImpl(
        user_providers_repo=providers_repo,
        user_ai_settings_repo=user_ai_repo,
        project_ai_settings_repo=project_ai_repo,
    )


# ---------------------------------------------------------------------------
# Tests - Cascade Priority
# ---------------------------------------------------------------------------


class TestCascadePriority:
    """Verify each cascade level is checked in the correct order."""

    async def test_project_intent_override_resolves(
        self,
    ) -> None:
        """Priority 1: Project-level intent override wins."""
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default-model",
            ),
            project_settings=FakeProjectSettings(
                novel_id=PROJECT_ID,
                intent_overrides={
                    "write": {
                        "provider_id": str(PROVIDER_ID),
                        "model_id": "project-intent-model",
                    },
                },
            ),
        )

        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, PROJECT_ID)
        assert result.config.model_id == "project-intent-model"
        assert result.source == "project_intent"

    async def test_project_category_override_resolves(
        self,
    ) -> None:
        """Priority 2: Project-level category override when no intent override."""
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default-model",
            ),
            project_settings=FakeProjectSettings(
                novel_id=PROJECT_ID,
                category_overrides={
                    "writing": {
                        "provider_id": str(PROVIDER_ID),
                        "model_id": "project-cat-model",
                    },
                },
            ),
        )

        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, PROJECT_ID)
        assert result.config.model_id == "project-cat-model"
        assert result.source == "project_category"

    async def test_user_intent_override_resolves(
        self,
    ) -> None:
        """Priority 3: User-level intent override when no project overrides."""
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default-model",
                intent_overrides={
                    "write": {
                        "provider_id": str(PROVIDER_ID),
                        "model_id": "user-intent-model",
                    },
                },
            ),
        )

        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, None)
        assert result.config.model_id == "user-intent-model"
        assert result.source == "user_intent"

    async def test_user_category_override_resolves(
        self,
    ) -> None:
        """Priority 4: User-level category override when no intent override."""
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default-model",
                category_overrides={
                    "writing": {
                        "provider_id": str(PROVIDER_ID),
                        "model_id": "user-cat-model",
                    },
                },
            ),
        )

        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, None)
        assert result.config.model_id == "user-cat-model"
        assert result.source == "user_category"

    async def test_user_default_model_resolves(
        self,
    ) -> None:
        """Priority 5: User's default model when no overrides."""
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default-model",
            ),
        )

        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, None)
        assert result.config.model_id == "default-model"
        assert result.source == "user_default"

    async def test_no_config_at_any_level_raises_configuration_error(
        self,
    ) -> None:
        """No provider configured -> ConfigurationError."""
        resolver = _make_resolver(
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=None,
                default_model="",
            ),
        )

        with pytest.raises(ConfigurationError, match="No AI provider configured"):
            await resolver.resolve(LLMIntent.WRITE, USER_ID, None)


# ---------------------------------------------------------------------------
# Tests - Cascade Ordering
# ---------------------------------------------------------------------------


class TestCascadeOrdering:
    """Verify that higher-priority levels win over lower ones."""

    async def test_project_intent_wins_over_project_category(
        self,
    ) -> None:
        """Project intent override takes precedence over project category."""
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default-model",
            ),
            project_settings=FakeProjectSettings(
                novel_id=PROJECT_ID,
                intent_overrides={
                    "write": {
                        "provider_id": str(PROVIDER_ID),
                        "model_id": "intent-model",
                    },
                },
                category_overrides={
                    "writing": {
                        "provider_id": str(PROVIDER_ID),
                        "model_id": "cat-model",
                    },
                },
            ),
        )

        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, PROJECT_ID)
        assert result.config.model_id == "intent-model"
        assert result.source == "project_intent"

    async def test_project_category_wins_over_user_intent(
        self,
    ) -> None:
        """Project category override takes precedence over user intent override."""
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default-model",
                intent_overrides={
                    "write": {
                        "provider_id": str(PROVIDER_ID),
                        "model_id": "user-intent-model",
                    },
                },
            ),
            project_settings=FakeProjectSettings(
                novel_id=PROJECT_ID,
                category_overrides={
                    "writing": {
                        "provider_id": str(PROVIDER_ID),
                        "model_id": "proj-cat-model",
                    },
                },
            ),
        )

        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, PROJECT_ID)
        assert result.config.model_id == "proj-cat-model"
        assert result.source == "project_category"

    async def test_user_intent_wins_over_user_category(
        self,
    ) -> None:
        """User intent override takes precedence over user category."""
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default-model",
                intent_overrides={
                    "sentiment": {
                        "provider_id": str(PROVIDER_ID),
                        "model_id": "intent-model",
                    },
                },
                category_overrides={
                    "analysis": {
                        "provider_id": str(PROVIDER_ID),
                        "model_id": "cat-model",
                    },
                },
            ),
        )

        result = await resolver.resolve(LLMIntent.SENTIMENT, USER_ID, None)
        assert result.config.model_id == "intent-model"
        assert result.source == "user_intent"
