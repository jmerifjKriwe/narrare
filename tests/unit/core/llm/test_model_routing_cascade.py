"""Tests for ModelRoutingResolver cascade - source metadata and edge cases.

Split from test_model_routing.py for RULE-04 compliance.
Tests the cascade priority, source metadata, and edge cases.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest

from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm.intents import LLMIntent

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
# Tests - Source Metadata
# ---------------------------------------------------------------------------


class TestSourceMetadata:
    """Verify source metadata is correct for each cascade level."""

    async def test_source_is_project_intent(
        self,
    ) -> None:
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            project_settings=FakeProjectSettings(
                novel_id=PROJECT_ID,
                intent_overrides={
                    "write": {"provider_id": str(PROVIDER_ID), "model_id": "m"},
                },
            ),
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default",
            ),
        )
        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, PROJECT_ID)
        assert result.source == "project_intent"

    async def test_source_is_project_category(
        self,
    ) -> None:
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            project_settings=FakeProjectSettings(
                novel_id=PROJECT_ID,
                category_overrides={
                    "writing": {"provider_id": str(PROVIDER_ID), "model_id": "m"},
                },
            ),
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default",
            ),
        )
        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, PROJECT_ID)
        assert result.source == "project_category"

    async def test_source_is_user_intent(
        self,
    ) -> None:
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default",
                intent_overrides={
                    "write": {"provider_id": str(PROVIDER_ID), "model_id": "m"},
                },
            ),
        )
        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, None)
        assert result.source == "user_intent"

    async def test_source_is_user_category(
        self,
    ) -> None:
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default",
                category_overrides={
                    "writing": {"provider_id": str(PROVIDER_ID), "model_id": "m"},
                },
            ),
        )
        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, None)
        assert result.source == "user_category"

    async def test_source_is_user_default(
        self,
    ) -> None:
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="gpt-4o",
            ),
        )
        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, None)
        assert result.source == "user_default"


# ---------------------------------------------------------------------------
# Tests - Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases for the cascade resolution."""

    async def test_intent_not_in_category_map_skips_category_level(
        self,
    ) -> None:
        """EMBED intent has no category - skips category level, goes to user default."""
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="embed-model",
                # Category overrides shouldn't apply to EMBED
                category_overrides={
                    "writing": {"provider_id": str(PROVIDER_ID), "model_id": "wrong-model"},
                },
            ),
        )

        result = await resolver.resolve(LLMIntent.EMBED, USER_ID, None)
        assert result.config.model_id == "embed-model"
        assert result.source == "user_default"

    async def test_no_project_id_skips_project_levels(
        self,
    ) -> None:
        """When project_id is None, project overrides are not checked."""
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default-model",
            ),
            # Even though project settings exist, they shouldn't be checked
            project_settings=FakeProjectSettings(
                novel_id=PROJECT_ID,
                category_overrides={
                    "writing": {"provider_id": str(PROVIDER_ID), "model_id": "project-model"},
                },
            ),
        )

        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, None)
        assert result.config.model_id == "default-model"
        assert result.source == "user_default"

    async def test_inactive_provider_in_override_falls_through(
        self,
    ) -> None:
        """If an override references an inactive provider, fall through to next level."""
        inactive_provider = _make_provider(is_active=False)
        active_provider = _make_provider(
            provider_id=uuid.uuid4(),
            provider_name="openai",
        )
        resolver = _make_resolver(
            providers=[inactive_provider, active_provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=active_provider.id,
                default_model="gpt-4o",
                category_overrides={
                    "writing": {
                        "provider_id": str(inactive_provider.id),
                        "model_id": "inactive-model",
                    },
                },
            ),
        )

        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, None)
        assert result.config.model_id == "gpt-4o"
        assert result.source == "user_default"

    async def test_resolved_model_contains_provider_name(
        self,
    ) -> None:
        """Resolved model config includes the provider name."""
        provider = _make_provider(provider_name="openrouter")
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="anthropic/claude-sonnet-4-5",
            ),
        )

        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, None)
        assert result.config.provider_name == "openrouter"
        assert result.config.model_id == "anthropic/claude-sonnet-4-5"

    async def test_resolved_model_contains_credentials(
        self,
    ) -> None:
        """Resolved model includes decrypted API key and base URL."""
        provider = _make_provider(base_url="https://custom.proxy/v1")
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="gpt-4o",
            ),
        )

        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, None)
        assert result.api_key is not None
        assert result.base_url == "https://custom.proxy/v1"

    async def test_empty_api_key_returns_none(
        self,
    ) -> None:
        """Provider with empty encrypted key -> api_key is None in result."""
        provider = _make_provider(api_key_encrypted="")
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="gpt-4o",
            ),
        )

        result = await resolver.resolve(LLMIntent.WRITE, USER_ID, None)
        assert result.api_key is None

    async def test_category_lookup_for_intent(
        self,
    ) -> None:
        """SENTIMENT maps to 'analysis' category - category override applies."""
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default-model",
                category_overrides={
                    "analysis": {"provider_id": str(PROVIDER_ID), "model_id": "analysis-model"},
                },
            ),
        )

        result = await resolver.resolve(LLMIntent.SENTIMENT, USER_ID, None)
        assert result.config.model_id == "analysis-model"
        assert result.source == "user_category"
