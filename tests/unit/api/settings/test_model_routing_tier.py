"""Tests for recommended_tier propagation through the ModelRoutingResolver.

Verifies that the backend resolver populates ``ResolvedModel.recommended_tier``
from ``IntentProfile.capability_tier`` and that different intents produce
different tiers.

Split from the former ``tests/unit/core/llm/test_model_routing_tier.py`` for
RULE-06 (one responsibility per file): the resolver-backed tests belong in the
API layer (they import ``narrare``), while the pure dataclass-shape tests stay
in ``tests/unit/core/llm/test_resolved_model.py``.
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
