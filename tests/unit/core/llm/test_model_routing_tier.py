"""Tests for ResolvedModel.recommended_tier propagation and backward compatibility.

Verifies that:
- ``ResolvedModel.recommended_tier`` defaults to None (backward compatible)
- The backend resolver populates it from ``IntentProfile.capability_tier``
- Different intents produce different tiers
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest

from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm import LLMIntent

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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

USER_ID = uuid.uuid4()
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
        is_active=is_active,
    )


def _make_resolver(
    *,
    providers: list[FakeProvider] | None = None,
    user_settings: FakeUserAiSettings | None = None,
) -> ModelRoutingResolverImpl:
    """Build a resolver with mocked repos."""
    from dataclasses import dataclass as _dc

    @_dc
    class _FakeProjectSettings:
        novel_id: uuid.UUID
        category_overrides: dict[str, Any] | None = None
        intent_overrides: dict[str, Any] | None = None
        token_limit_overrides: dict[str, Any] | None = None

    _providers = providers or []
    _user_settings = user_settings or FakeUserAiSettings(user_id=USER_ID)

    providers_repo = AsyncMock()
    providers_repo.get = AsyncMock(
        side_effect=lambda pid: next((p for p in _providers if p.id == pid), None)
    )

    user_ai_repo = AsyncMock()
    user_ai_repo.get = AsyncMock(return_value=_user_settings)

    project_ai_repo = AsyncMock()
    project_ai_repo.get = AsyncMock(return_value=_FakeProjectSettings(novel_id=uuid.uuid4()))

    return ModelRoutingResolverImpl(
        user_providers_repo=providers_repo,
        user_ai_settings_repo=user_ai_repo,
        project_ai_settings_repo=project_ai_repo,
    )


# ---------------------------------------------------------------------------
# Tests - ResolvedModel dataclass (backward compatibility)
# ---------------------------------------------------------------------------


class TestResolvedModelDataclass:
    """Verify ResolvedModel fields, defaults, and backward compatibility."""

    def test_recommended_tier_defaults_to_none(self) -> None:
        """recommended_tier is optional and defaults to None."""
        from narrare_core.llm.model_config import ResolvedModelConfig
        from narrare_core.llm.model_routing import ResolvedModel

        config = ResolvedModelConfig(
            provider_name="openai",
            model_id="gpt-4o",
        )
        model = ResolvedModel(config=config)
        assert model.recommended_tier is None

    def test_recommended_tier_can_be_set(self) -> None:
        """recommended_tier can be explicitly provided."""
        from narrare_core.llm.model_config import ResolvedModelConfig
        from narrare_core.llm.model_routing import ResolvedModel

        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
        )
        model = ResolvedModel(config=config, recommended_tier="creative")
        assert model.recommended_tier == "creative"

    def test_backward_compatible_without_recommended_tier(self) -> None:
        """Existing code that doesn't pass recommended_tier still works."""
        from narrare_core.llm.model_config import ResolvedModelConfig
        from narrare_core.llm.model_routing import ResolvedModel

        config = ResolvedModelConfig(
            provider_name="openai",
            model_id="gpt-4o",
        )
        # Old-style construction — no recommended_tier
        model = ResolvedModel(
            config=config,
            api_key="sk-test",
            base_url=None,
            source="user_default",
        )
        assert model.config.model_id == "gpt-4o"
        assert model.source == "user_default"
        assert model.recommended_tier is None


# ---------------------------------------------------------------------------
# Tests - Recommended Tier propagation through resolver
# ---------------------------------------------------------------------------


class TestRecommendedTier:
    """Verify that recommended_tier is populated from IntentProfile."""

    async def test_user_default_populates_recommended_tier(self) -> None:
        """User default model carries recommended_tier from intent profile."""
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
        # WRITE → IntentProfile(capability_tier="creative")
        assert result.recommended_tier == "creative"
        assert result.source == "user_default"

    async def test_override_populates_recommended_tier(self) -> None:
        """Override resolution also carries recommended_tier."""
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default-model",
                intent_overrides={
                    "analyse": {
                        "provider_id": str(PROVIDER_ID),
                        "model_id": "override-model",
                    },
                },
            ),
        )

        result = await resolver.resolve(LLMIntent.ANALYSE, USER_ID, None)
        # ANALYSE → IntentProfile(capability_tier="reasoning")
        assert result.recommended_tier == "reasoning"
        assert result.source == "user_intent"

    async def test_different_intents_different_tiers(self) -> None:
        """Each intent gets its own capability tier."""
        provider = _make_provider()
        resolver = _make_resolver(
            providers=[provider],
            user_settings=FakeUserAiSettings(
                user_id=USER_ID,
                default_provider_id=PROVIDER_ID,
                default_model="default-model",
            ),
        )

        # SENTIMENT → "fast"
        result_fast = await resolver.resolve(LLMIntent.SENTIMENT, USER_ID, None)
        assert result_fast.recommended_tier == "fast"

        # SUMMARIZE → "fast"
        result_summ = await resolver.resolve(LLMIntent.SUMMARIZE, USER_ID, None)
        assert result_summ.recommended_tier == "fast"

        # CHAT → "balanced"
        result_chat = await resolver.resolve(LLMIntent.CHAT, USER_ID, None)
        assert result_chat.recommended_tier == "balanced"
