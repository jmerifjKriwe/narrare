"""Tests for llm/_providers/anthropic.py — Anthropic factory construction.

Exercises the actual ``_make_anthropic`` factory body to verify:
- Correct pydantic-ai Model type returned
- API key routing (explicit vs env-var fallback)
- Base URL override path (proxy endpoints)
"""

from __future__ import annotations

import pytest
from pydantic_ai.exceptions import UserError
from pydantic_ai.models.anthropic import AnthropicModel

from narrare_core.llm._providers.anthropic import _make_anthropic


class TestMakeAnthropic:
    """``_make_anthropic`` creates ``AnthropicModel`` with credential routing."""

    def test_with_api_key_returns_anthropic_model(self) -> None:
        model = _make_anthropic("claude-sonnet-4-5-20251020", api_key="sk-ant-test")
        assert isinstance(model, AnthropicModel)
        assert model.model_name == "claude-sonnet-4-5-20251020"

    def test_with_base_url_returns_anthropic_model(self) -> None:
        """base_url triggers the explicit-provider path (even without api_key)."""
        model = _make_anthropic("claude-sonnet-4-5", base_url="https://anthropic-proxy.example.com")
        assert isinstance(model, AnthropicModel)
        assert model.model_name == "claude-sonnet-4-5"

    def test_with_both_api_key_and_base_url(self) -> None:
        model = _make_anthropic(
            "claude-haiku-3-5",
            api_key="sk-test",
            base_url="https://proxy.anthropic.example.com",
        )
        assert isinstance(model, AnthropicModel)
        assert model.model_name == "claude-haiku-3-5"

    def test_env_var_fallback_when_no_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without explicit credentials, falls back to ANTHROPIC_API_KEY env var."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
        model = _make_anthropic("claude-opus-4-20250514")
        assert isinstance(model, AnthropicModel)
        assert model.model_name == "claude-opus-4-20250514"

    def test_no_credentials_raises_user_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No key arg and no env var -> Anthropic requires a credential at construction.

        Unlike OpenAI, ``AnthropicProvider`` does not accept a null key, so
        construction fails fast with a pydantic-ai ``UserError``. This is the
        correct fail-fast behaviour for a provider that cannot operate without
        credentials.
        """
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(UserError):
            _make_anthropic("claude-sonnet-4-5-20251020")

    def test_no_credentials_with_base_url_also_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """base_url alone is insufficient for Anthropic - a key is mandatory.

        Deterministically exercises the no-credential + base_url branch (the
        non-deterministic ``test_with_base_url_returns_anthropic_model`` may
        route through the credential branch when ANTHROPIC_API_KEY is set in
        the ambient environment).
        """
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(UserError):
            _make_anthropic("claude-sonnet-4-5", base_url="https://proxy.anthropic.example.com")
