"""Tests for Pydantic override schemas — CategoryOverride, IntentOverride, TokenLimitOverride."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from narrare_core.llm.override_schemas import (
    CategoryOverride,
    IntentOverride,
    TokenLimitOverride,
)


class TestCategoryOverride:
    def test_valid_category_override_with_uuid_and_model_id(self) -> None:
        provider_id = uuid.uuid4()
        override = CategoryOverride(provider_id=provider_id, model_id="claude-sonnet-4-5-20251020")
        assert override.provider_id == provider_id
        assert override.model_id == "claude-sonnet-4-5-20251020"

    def test_category_override_from_dict(self) -> None:
        provider_id = uuid.uuid4()
        override = CategoryOverride.model_validate(
            {
                "provider_id": str(provider_id),
                "model_id": "gpt-4o",
            }
        )
        assert override.provider_id == provider_id

    def test_category_override_missing_provider_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            CategoryOverride(model_id="gpt-4o")  # type: ignore[call-arg]

    def test_category_override_missing_model_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            CategoryOverride(provider_id=uuid.uuid4())  # type: ignore[call-arg]


class TestIntentOverride:
    def test_valid_intent_override(self) -> None:
        provider_id = uuid.uuid4()
        override = IntentOverride(provider_id=provider_id, model_id="gpt-4o-mini")
        assert override.provider_id == provider_id
        assert override.model_id == "gpt-4o-mini"

    def test_intent_override_from_dict(self) -> None:
        provider_id = uuid.uuid4()
        override = IntentOverride.model_validate(
            {
                "provider_id": str(provider_id),
                "model_id": "anthropic/claude-sonnet-4-5",
            }
        )
        assert override.model_id == "anthropic/claude-sonnet-4-5"

    def test_intent_override_missing_fields_raises(self) -> None:
        with pytest.raises(ValidationError):
            IntentOverride(provider_id=uuid.uuid4())  # type: ignore[call-arg]


class TestTokenLimitOverride:
    def test_valid_token_limit_override_with_defaults(self) -> None:
        override = TokenLimitOverride(max_tokens=2000, temperature=0.7)
        assert override.max_tokens == 2000
        assert override.temperature == 0.7

    def test_valid_with_max_tokens_and_temperature(self) -> None:
        override = TokenLimitOverride(max_tokens=500, temperature=0.2)
        assert override.max_tokens == 500
        assert override.temperature == 0.2

    def test_invalid_max_tokens_zero_raises(self) -> None:
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            TokenLimitOverride(max_tokens=0, temperature=0.7)

    def test_invalid_max_tokens_negative_raises(self) -> None:
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            TokenLimitOverride(max_tokens=-1, temperature=0.7)

    def test_invalid_temperature_below_zero_raises(self) -> None:
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            TokenLimitOverride(max_tokens=100, temperature=-0.1)

    def test_invalid_temperature_above_two_raises(self) -> None:
        with pytest.raises(ValidationError, match="less than or equal to 2"):
            TokenLimitOverride(max_tokens=100, temperature=2.1)

    def test_invalid_temperature_far_above_raises(self) -> None:
        with pytest.raises(ValidationError, match="less than or equal to 2"):
            TokenLimitOverride(max_tokens=100, temperature=3.0)


class TestTokenLimitEdgeCases:
    def test_max_tokens_one_is_valid(self) -> None:
        """Edge case: max_tokens=1 is the minimum valid value."""
        override = TokenLimitOverride(max_tokens=1, temperature=0.7)
        assert override.max_tokens == 1

    def test_temperature_zero_is_valid(self) -> None:
        """Edge case: temperature=0.0 is valid (deterministic output)."""
        override = TokenLimitOverride(max_tokens=100, temperature=0.0)
        assert override.temperature == 0.0

    def test_temperature_two_is_valid(self) -> None:
        """Edge case: temperature=2.0 is the maximum valid value."""
        override = TokenLimitOverride(max_tokens=100, temperature=2.0)
        assert override.temperature == 2.0

    def test_large_max_tokens_is_valid(self) -> None:
        """No upper bound on max_tokens in the schema."""
        override = TokenLimitOverride(max_tokens=200000, temperature=0.7)
        assert override.max_tokens == 200000
